from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from datetime import datetime, timedelta
from sqlalchemy import func, and_

from models import db, SessaoUso, Historico, Agendamento, Notebook
from auth import login_required, permission_required
from utils import trigger_iot_relay

movements_bp = Blueprint('movements', __name__)

def extrair_ids_limpos(lista_ids_str):
    """Limpa e extrai os IDs, tratando erros de leitura de leitores USB e teclados ABNT2"""
    cleaned_ids = []
    for id_cru in lista_ids_str.split(','):
        id_cru = id_cru.strip().upper()
        if not id_cru: continue
        # Se o leitor leu a URL completa do QR Code (ex: HTTPSÇ;;10...;NOTEBOOK;00001)
        if 'NOTEBOOK' in id_cru:
            id_cru = id_cru.replace(';', '/').replace('\\', '/').replace('Ç', ':')
            id_cru = id_cru.split('/')[-1]
        cleaned_ids.append(id_cru)
    return list(set([x.zfill(5) if x.isdigit() else x for x in cleaned_ids]))

def get_periodo_atual():
    hora = datetime.now().hour
    if hora < 12: return 'Matutino'
    elif hora < 18: return 'Vespertino'
    else: return 'Noturno'

@movements_bp.route('/sessoes')
@login_required
def sessoes():
    if not request.args:
        data_inicio = datetime.now().strftime('%Y-%m-%d')
        data_fim = datetime.now().strftime('%Y-%m-%d')
    else:
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        
    busca = request.args.get('busca', '').strip()
    
    # Subquery para concatenar os IDs dos itens
    subquery_itens = db.session.query(
        func.group_concat(Historico.id_etiqueta, ', ')
    ).filter(
        Historico.data == SessaoUso.data_inicio,
        Historico.acao == 'Saída/Empréstimo'
    ).correlate(SessaoUso).scalar_subquery()

    query = db.session.query(
        SessaoUso,
        SessaoUso.data_inicio.label('data_formatada'),
        subquery_itens.label('lista_itens')
    )
    
    if data_inicio:
        query = query.filter(SessaoUso.data_inicio >= datetime.strptime(f"{data_inicio} 00:00:00", '%Y-%m-%d %H:%M:%S'))
    if data_fim:
        query = query.filter(SessaoUso.data_inicio <= datetime.strptime(f"{data_fim} 23:59:59", '%Y-%m-%d %H:%M:%S'))
        
    if busca:
        busca_like = f"%{busca}%"
        query = query.filter(
            (SessaoUso.professor.like(busca_like)) |
            (SessaoUso.turma.like(busca_like)) |
            (SessaoUso.observacoes.like(busca_like))
        )
        
    sessoes_brutas = query.order_by(SessaoUso.data_inicio.desc()).all()
    sessoes_lista = []
    for row in sessoes_brutas:
        try:
            row.SessaoUso.data_formatada = datetime.fromisoformat(str(row.SessaoUso.data_inicio)).strftime('%d/%m/%Y %H:%M')
        except (ValueError, TypeError):
            row.SessaoUso.data_formatada = str(row.SessaoUso.data_inicio or '')
        row.SessaoUso.lista_itens = row.lista_itens
        sessoes_lista.append(row.SessaoUso)
    return render_template('sessoes.html', sessoes=sessoes_lista, data_inicio=data_inicio, data_fim=data_fim, filtro_busca=busca)

@movements_bp.route('/sessoes/registrar', methods=('GET', 'POST'))
@permission_required('perm_movimentacao')
def registrar_sessao():
    agendamento_id = request.args.get('agendamento_id')
    
    preenchimento = {'turma': '', 'professor': '', 'lista_ids': ''}

    if agendamento_id and request.method == 'GET':
        # Funcionalidade Inteligente: Mover agendamento para saída com apenas 1 clique
        # Redireciona imediatamente para a efetivação instantânea sem pedir para preencher o formulário
        return redirect(url_for('movements.efetivar_agendamento', agendamento_id=agendamento_id))

    if request.method == 'POST':
        preenchimento['turma'] = request.form.get('turma', '').strip()
        
        # Generalizado: 'professor' agora é 'responsavel'
        if session.get('perm_config') == 1:
            preenchimento['responsavel'] = request.form.get('responsavel', '').strip()
        else:
            preenchimento['responsavel'] = session.get('username', '')
            
        preenchimento['lista_ids'] = request.form.get('lista_ids', '')
        
        destino = preenchimento['turma']
        responsavel = preenchimento['responsavel']
        lista_ids_str = preenchimento['lista_ids']
        
        programa = request.form.get('programa', 'Uso rotineiro')
        observacoes = request.form.get('observacoes', '')
        
        # Combina a data e a hora em uma única string (se as duas foram preenchidas)
        previsao_data = request.form.get('previsao_data', '').strip()
        previsao_hora = request.form.get('previsao_hora', '').strip()
        previsao_devolucao = datetime.strptime(f"{previsao_data} {previsao_hora}", '%Y-%m-%d %H:%M') if previsao_data and previsao_hora else None
        
        if previsao_data and previsao_hora:
            try:
                dt_previsao = datetime.strptime(f"{previsao_data} {previsao_hora}", "%Y-%m-%d %H:%M")
                if dt_previsao < datetime.now():
                    flash('Erro: A previsão de devolução não pode ser uma data ou horário no passado.', 'error')
                    return redirect(request.url)
            except Exception:
                pass

        if not lista_ids_str:
            flash('Nenhum equipamento foi selecionado.', 'error')
            return render_template('registrar_sessao.html', preenchimento=preenchimento)

        ids_list = extrair_ids_limpos(lista_ids_str)
        
        if not ids_list:
            flash('Nenhum equipamento válido foi identificado na leitura.', 'error')
            return render_template('registrar_sessao.html', preenchimento=preenchimento)
            
        quantidade = len(ids_list)
        
        # --- VERIFICAÇÃO DE PENDÊNCIAS COM SQLAlchemy ---
        limit_date = datetime.now() - timedelta(hours=24)
        
        # Subquery para encontrar a data da última saída de um notebook
        subquery_last_saida = db.session.query(func.max(Historico.data)).filter(
            Historico.id_etiqueta == Notebook.id,
            Historico.acao == 'Saída/Empréstimo'
        ).correlate(Notebook).scalar_subquery()

        pendencia = db.session.query(SessaoUso.turma, func.strftime('%d/%m %H:%M', SessaoUso.data_inicio)).join(
            Historico, SessaoUso.data_inicio == Historico.data
        ).join(Notebook, Historico.id_etiqueta == Notebook.id).filter(
            SessaoUso.professor == responsavel, SessaoUso.data_inicio < limit_date, Notebook.status == 'Em uso', Historico.acao == 'Saída/Empréstimo', Historico.data == subquery_last_saida
        ).first()

        if pendencia and pendencia.turma:
            ignorar_bloqueio = request.form.get('ignorar_bloqueio') == '1'
            is_admin = session.get('perm_config', 0) == 1

            if is_admin and ignorar_bloqueio:
                flash(f"ALERTA ADMIN: Saída forçada para '{responsavel}'.", 'warning')
            else:
                flash(f"BLOQUEIO: O colaborador(a) '{responsavel}' possui pendências.", 'error')
                return render_template('registrar_sessao.html', preenchimento=preenchimento)

        itens_banco = Notebook.query.filter(Notebook.id.in_(ids_list)).all()
        itens_encontrados = {item.id: item.status for item in itens_banco}
        nao_cadastrados = [x for x in ids_list if x not in itens_encontrados]
        if nao_cadastrados:
            flash(f'BLOQUEIO: Itens não cadastrados: {", ".join(nao_cadastrados)}', 'error')
            return render_template('registrar_sessao.html', preenchimento=preenchimento)
            
        em_manutencao = [id_chk for id_chk, status in itens_encontrados.items() if status == 'Em manutenção']
        if em_manutencao:
            flash(f'BLOQUEIO: Itens em manutenção: {", ".join(em_manutencao)}', 'error')
            return render_template('registrar_sessao.html', preenchimento=preenchimento)
        
        ja_em_uso = [id_chk for id_chk, status in itens_encontrados.items() if status == 'Em uso']
        if ja_em_uso:
            flash(f'BLOQUEIO: Equipamentos já estão em uso por outra pessoa: {", ".join(ja_em_uso)}', 'error')
            return render_template('registrar_sessao.html', preenchimento=preenchimento)
        
        hoje = datetime.now().strftime('%Y-%m-%d')
        periodo_atual = get_periodo_atual()
        data_movimentacao = datetime.now()
        
        agendamento_vinculado = request.form.get('agendamento_vinculado')
        if agendamento_vinculado:
            ag_vinc = db.session.get(Agendamento, agendamento_vinculado) # MODERNIZADO
            if ag_vinc: ag_vinc.status = 'Realizado'
        else:
            agendamento_pendente = Agendamento.query.filter_by(solicitante=responsavel, data_uso=hoje, periodo=periodo_atual, status='Agendado').first()
            if agendamento_pendente:
                agendamento_pendente.status = 'Realizado'
                flash(f"Agendamento de '{responsavel}' baixado automaticamente.", 'success')

        nova_sessao = SessaoUso(
            turma=destino, professor=responsavel, programa=programa, quantidade_notebooks=quantidade,
            data_inicio=data_movimentacao, observacoes=observacoes, previsao_devolucao=previsao_devolucao,
            usuario_movimentacao=session.get('username', 'Sistema')
        )
        db.session.add(nova_sessao)
        
        for notebook_id in ids_list:
            nb = db.session.get(Notebook, notebook_id)
            if nb:
                nb.status = 'Em uso'
                nb.localizacao = destino
            obs_hist = f"Destino/Setor: {destino}"
            novo_historico = Historico(id_etiqueta=notebook_id, acao='Saída/Empréstimo', usuario_movimentacao=session.get('username', 'Sistema'), responsavel=responsavel, data=data_movimentacao, obs=obs_hist)
            db.session.add(novo_historico)

        db.session.commit()
        flash(f'Tudo certo! A saída de <b>{quantidade} equipamento(s)</b> para <b>{responsavel}</b> foi registrada com sucesso!', 'success')
        if request.args.get('kiosk'):
            return redirect(url_for('kiosk_home'))
        return redirect(url_for('dashboard'))

    # --- MÁGICA DO AUTOCOMPLETAR (Busca todos os nomes já usados no sistema) ---
    profs_query = db.session.query(SessaoUso.professor).filter(SessaoUso.professor != None, SessaoUso.professor != '').distinct()
    sols_query = db.session.query(Agendamento.solicitante).filter(Agendamento.solicitante != None, Agendamento.solicitante != '').distinct()
    
    nomes_unicos = {p.professor for p in profs_query} | {s.solicitante for s in sols_query}
    nomes_historico = sorted(list(nomes_unicos))
    
    return render_template('registrar_sessao.html', preenchimento=preenchimento, nomes_historico=nomes_historico)

@movements_bp.route('/sessoes/efetivar_agendamento/<int:agendamento_id>')
@permission_required('perm_movimentacao')
def efetivar_agendamento(agendamento_id):
    agendamento = db.session.get(Agendamento, agendamento_id) # MODERNIZADO
    
    if not agendamento or agendamento.status != 'Agendado':
        flash('Agendamento inválido ou já processado.', 'error')
        if request.args.get('kiosk'):
            return redirect(url_for('movements.resgatar', kiosk=1))
        return redirect(request.referrer or url_for('dashboard'))
        
    turma = agendamento.finalidade
    responsavel = agendamento.solicitante
    lista_ids_str = agendamento.itens_reservados
    
    if not lista_ids_str:
        flash('Este agendamento não possui itens específicos selecionados.', 'error')
        if request.args.get('kiosk'):
            return redirect(url_for('movements.resgatar', kiosk=1))
        return redirect(request.referrer or url_for('dashboard'))
        
    ids_list = extrair_ids_limpos(lista_ids_str)
    quantidade = len(ids_list)
    
    previsao_devolucao = ""
    if agendamento.data_uso and agendamento.horario_devolucao:
        previsao_devolucao = datetime.strptime(f"{agendamento.data_uso} {agendamento.horario_devolucao}", '%Y-%m-%d %H:%M')

    # CORREÇÃO: Redireciona para a API que confirma a saída, centralizando a lógica
    return redirect(url_for('iot_confirmar_saida', agendamento_id=agendamento_id, kiosk=request.args.get('kiosk')))
@movements_bp.route('/sessoes/efetivar_codigo/<string:codigo>')
@permission_required('perm_movimentacao')
def efetivar_codigo(codigo):
    agendamento = Agendamento.query.filter_by(codigo_reserva=codigo.upper(), status='Agendado').first()
    if agendamento:
        return redirect(url_for('movements.efetivar_agendamento', agendamento_id=agendamento.id, kiosk=request.args.get('kiosk')))
        
    # 2. Tenta Devolução (Mágica Anti-Cache: Se o Kiosk antigo forçou a rota de saída, redirecionamos para a devolução)
    ag_dev = Agendamento.query.filter_by(codigo_reserva=codigo.upper(), status='Realizado').first()
    if ag_dev:
        return redirect(url_for('movements.registrar_devolucao', kiosk=request.args.get('kiosk'), auto_load=codigo.upper()))

    flash(f'Código {codigo} inválido, não encontrado ou agendamento já finalizado.', 'error')
    if request.args.get('kiosk'):
        return redirect(url_for('kiosk_home'))
    return redirect(request.referrer or url_for('dashboard'))

@movements_bp.route('/resgatar', methods=['GET'])
@permission_required('perm_movimentacao')
def resgatar():
    return render_template('resgatar_kiosk.html')

@movements_bp.route('/sessoes/devolucao', methods=('GET', 'POST'))
@permission_required('perm_movimentacao')
def registrar_devolucao():
    if request.method == 'POST':
        lista_ids_str = request.form.get('lista_ids', '') # MODERNIZADO
        observacoes = request.form.get('observacoes', '')
        responsavel_devolucao = request.form.get('responsavel_devolucao', '').strip().upper() or session.get('username', 'Sistema').upper()

        if not lista_ids_str:
            flash('Nenhum equipamento escaneado.', 'error')
            return redirect(url_for('movements.registrar_devolucao'))

        ids_list = extrair_ids_limpos(lista_ids_str)
        quantidade = len(ids_list)
        
        itens_banco = Notebook.query.filter(Notebook.id.in_(ids_list)).all()
        itens_encontrados = {item.id: item.status for item in itens_banco}
        nao_cadastrados = [x for x in ids_list if x not in itens_encontrados]
        if nao_cadastrados:
            flash(f'Itens não cadastrados: {", ".join(nao_cadastrados)}', 'error')
            return redirect(url_for('movements.registrar_devolucao'))
            
        ja_disponivel = [id_chk for id_chk, status in itens_encontrados.items() if status == 'Disponível']
        if ja_disponivel:
            flash(f'ATENÇÃO: Os equipamentos a seguir já estão disponíveis no estoque: {", ".join(ja_disponivel)}', 'warning')
            return redirect(url_for('movements.registrar_devolucao'))
            
        for notebook_id in ids_list:
            nb = db.session.get(Notebook, notebook_id)
            if nb:
                agora = datetime.now()
                reserva_futura = Agendamento.query.filter(
                    Agendamento.status == 'Agendado',
                    Agendamento.itens_reservados.like(f'%{notebook_id}%')
                ).all()
                tem_reserva_futura = any(
                    ag.data_uso and (
                        ag.data_uso > agora.strftime('%Y-%m-%d') or
                        (ag.data_uso == agora.strftime('%Y-%m-%d') and
                         (ag.horario_retirada or '23:59') >= agora.strftime('%H:%M'))
                    )
                    for ag in reserva_futura
                )
                nb.status = 'Reservado' if tem_reserva_futura else 'Disponível'
            obs_hist = f"Devolução registrada. {observacoes}"
            novo_historico = Historico(id_etiqueta=notebook_id, acao='Devolução', usuario_movimentacao=session.get('username', 'Sistema'), responsavel=responsavel_devolucao, data=datetime.now(), obs=obs_hist)
            db.session.add(novo_historico)

        db.session.commit()
        if request.args.get('kiosk'):
            iot_enabled = getattr(g, 'modules', {}).get('iot', False)
            trigger_iot_relay(force_open=iot_enabled)
            if iot_enabled:
                flash(f'Devolução Recebida! 🔓<br><br>A porta foi destravada. Pode guardar os <b>{quantidade} equipamento(s)</b>.', 'success')
            else:
                flash(f'Devolução de <b>{quantidade} equipamento(s)</b> registrada com sucesso!', 'success')
            return redirect(url_for('kiosk_home'))
            
        flash(f'Excelente! A devolução de <b>{quantidade} equipamento(s)</b> foi confirmada e o estoque já foi atualizado.', 'success')
        return redirect(url_for('dashboard'))
        
    # --- MÁGICA DO AUTOCOMPLETAR PARA DEVOLUÇÕES ---
    observacoes = db.session.query(Historico.obs).filter(Historico.acao == 'Devolução', Historico.obs != None, Historico.obs != '').distinct().all()
    obs_unicas = set()    
    for o in observacoes:
        texto = o.obs.replace("Devolução registrada.", "").strip()
        if texto: obs_unicas.add(texto)
    obs_historico = sorted(list(obs_unicas))
    
    return render_template('registrar_devolucao.html', obs_historico=obs_historico)

@movements_bp.route('/historico/devolucoes')
@login_required
def historico_devolucoes():
    if not request.args:
        data_inicio = datetime.now().strftime('%Y-%m-%d')
        data_fim = datetime.now().strftime('%Y-%m-%d')
    else:
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
        
    busca = request.args.get('busca', '').strip()
    
    query = db.session.query(
        Historico, 
        Historico.data.label('data_formatada'),
        Notebook.modelo,
        Notebook.tipo
    ).outerjoin(Notebook, Historico.id_etiqueta == Notebook.id).filter(Historico.acao == 'Devolução')
    
    if data_inicio:
        dt_inicio_obj = datetime.strptime(f"{data_inicio} 00:00:00", '%Y-%m-%d %H:%M:%S')
        query = query.filter(Historico.data >= dt_inicio_obj)
    if data_fim:
        dt_fim_obj = datetime.strptime(f"{data_fim} 23:59:59", '%Y-%m-%d %H:%M:%S')
        query = query.filter(Historico.data <= dt_fim_obj)
        
    if busca:
        busca_like = f"%{busca}%"
        query = query.filter(
            (Historico.id_etiqueta.like(busca_like)) | (Notebook.modelo.like(busca_like)) |
            (Notebook.tipo.like(busca_like)) | (Historico.usuario_movimentacao.like(busca_like)) |
            (Historico.obs.like(busca_like))
        )
        
    devolucoes_brutas = query.order_by(Historico.data.desc()).all()
    devolucoes = []
    for row in devolucoes_brutas:
        historico = row.Historico
        data_raw = historico.data
        if isinstance(row.data_formatada, datetime):
            data_formatada = row.data_formatada.strftime('%d/%m/%Y %H:%M')
        else:
            try:
                data_formatada = datetime.fromisoformat(str(data_raw)).strftime('%d/%m/%Y %H:%M')
            except (ValueError, TypeError):
                data_formatada = str(data_raw or '')

        devolucoes.append({
            'data': data_raw,
            'data_formatada': data_formatada,
            'id_etiqueta': historico.id_etiqueta,
            'tipo': row.tipo,
            'modelo': row.modelo,
            'tipo_movimentacao': historico.acao or 'Devolução',
            'usuario_movimentacao': historico.usuario_movimentacao,
            'responsavel_devolucao': (
                historico.responsavel
                if historico.responsavel and historico.responsavel != '-'
                else historico.usuario_movimentacao or '-'
            ),
            'obs': historico.obs
        })

    return render_template('historico_devolucoes.html', 
                           devolucoes=devolucoes,
                           data_inicio=data_inicio,
                           data_fim=data_fim,
                           filtro_busca=busca)
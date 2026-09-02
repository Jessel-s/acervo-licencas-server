from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from sqlalchemy import func
import logging

from models import db, Problema, Notebook, Historico
from auth import login_required, permission_required

maintenance_bp = Blueprint('maintenance', __name__)

@maintenance_bp.route('/manutencao/dashboard')
@permission_required('perm_chamados')
def dashboard():
    # KPIs (Indicadores Principais)
    abertos = Problema.query.filter_by(status='Aberto').count()
    criticos = Problema.query.filter(Problema.status == 'Aberto', Problema.prioridade.in_(['Alta', 'Crítica'])).count()
    resolvidos = Problema.query.filter_by(status='Resolvido').count()
    
    # Dados para Gráfico: Chamados por Categoria (Abertos)
    cat_data = db.session.query(Problema.categoria, func.count(Problema.id).label('qtd')).filter(Problema.status == 'Aberto').group_by(Problema.categoria).all()
    
    # Dados para Gráfico: Prioridades (Abertos)
    prio_data = db.session.query(Problema.prioridade, func.count(Problema.id).label('qtd')).filter(Problema.status == 'Aberto').group_by(Problema.prioridade).all()
    
    # Fila Rápida: 5 Chamados Mais Recentes
    recentes = db.session.query(
        Problema.id, Problema.local_incidente, Problema.notebook_id, Problema.categoria,
        Problema.prioridade, Problema.tipo_problema,
        Problema.data_registro.label('data_fmt') # O template irá formatar
    ).filter(Problema.status == 'Aberto').order_by(Problema.data_registro.desc()).limit(5).all()

    return render_template('helpdesk_dashboard.html', 
                           abertos=abertos, 
                           criticos=criticos, 
                           resolvidos=resolvidos,
                           cat_data=[row._asdict() for row in cat_data],
                           prio_data=[row._asdict() for row in prio_data],
                           recentes=recentes)

@maintenance_bp.route('/problemas')
@permission_required('perm_chamados')
def problemas():
    # CORREÇÃO DEFINITIVA: The debug log proved the error happens when reading from the 'problemas' table,
    # indicating data corruption (a string in a date column). This query now reads the date columns
    # as raw text (`cast(..., Text)`) to prevent SQLAlchemy from crashing during type conversion.
    # The conversion is then handled safely in Python.
    from sqlalchemy import cast, Text
    chamados_query = db.session.query(
        Problema.id, Problema.notebook_id, Problema.tipo_problema, Problema.descricao,
        cast(Problema.data_registro, Text).label('data_registro_raw'), # Lê a data como texto puro
        Problema.responsavel, Problema.status, Problema.prioridade,
        Problema.categoria, Problema.parecer_tecnico, Problema.local_incidente
    ).order_by(Problema.id.desc()).all() # Ordena por ID para evitar erro na ordenação por data corrompida

    # Safely convert results to a list of dictionaries and handle date conversion
    chamados = [p._asdict() for p in chamados_query]
    for p in chamados:
        data_raw = p.get('data_registro_raw')
        p['data_formatada'] = ''
        if data_raw:
            try:
                # Tenta converter a string para data; se falhar (dado corrompido), ignora.
                data_obj = datetime.fromisoformat(data_raw)
                p['data_formatada'] = data_obj.strftime('%d/%m/%Y %H:%M')
            except (ValueError, TypeError):
                pass # Ignora a formatação se o dado for inválido (ex: '2026')

    abertos = [p for p in chamados if p.get('status') == 'Aberto']
    resolvidos = [p for p in chamados if p.get('status') == 'Resolvido']
    
    return render_template('problemas.html', abertos=abertos, resolvidos=resolvidos)

@maintenance_bp.route('/manutencao/novo', methods=['GET', 'POST'])
@permission_required('perm_movimentacao')
def nova_manutencao():
    if request.method == 'POST':
        categoria = request.form.get('categoria', 'OUTROS').strip().upper()
        prioridade = request.form.get('prioridade', 'Normal').strip()
        tipo_problema = request.form.get('tipo_problema', '').strip().upper()
        descricao = request.form.get('descricao', '').strip().upper()
        local_incidente = request.form.get('local_incidente', 'NÃO INFORMADO').strip().upper()
        patrimonio = request.form.get('patrimonio', '').strip().upper()
        responsavel = session.get('username', 'Sistema')

        # Limpeza caso o leitor USB leia a URL completa do QR Code com teclado desconfigurado
        if 'ATIVO' in patrimonio or 'NOTEBOOK' in patrimonio:
            patrimonio = patrimonio.replace(';', '/').replace('\\', '/').replace('Ç', ':')
            patrimonio = patrimonio.split('/')[-1]

        notebook_id = None

        # Se digitou um patrimônio, tentamos achar no banco para bloquear ele
        if patrimonio:
            if patrimonio.isdigit():
                patrimonio = patrimonio.zfill(5)
            
            # CORREÇÃO: Atualiza diretamente sem carregar o objeto, evitando o erro de conversão de data.
            rows_updated = Notebook.query.filter_by(id=patrimonio).update({'status': 'Em manutenção'})
            
            if rows_updated > 0:
                notebook_id = patrimonio
            else:
                flash(f'Aviso: O Patrimônio "{patrimonio}" não foi encontrado. O chamado foi aberto sem vínculo a um ativo.', 'warning')

        novo_problema = Problema(
            notebook_id=notebook_id, local_incidente=local_incidente, categoria=categoria,
            prioridade=prioridade, tipo_problema=tipo_problema, descricao=descricao,
            responsavel=responsavel, status='Aberto'
        )
        db.session.add(novo_problema)
        db.session.commit() # CORREÇÃO: Salva o novo chamado no banco de dados.

        flash('Chamado aberto com sucesso!<br><br>A equipe de TI foi notificada e o status do equipamento foi atualizado.', 'success')
        if request.args.get('kiosk'):
            return redirect(url_for('kiosk_home'))
        return redirect(url_for('dashboard'))

    return render_template('reportar_problema.html', notebook=None)

@maintenance_bp.route('/notebook/<string:notebook_id>/reportar_problema', methods=('GET', 'POST'))
@permission_required('perm_movimentacao')
def reportar_problema(notebook_id):
    if notebook_id.isdigit():
        notebook_id = notebook_id.zfill(5)
        
    # CORREÇÃO: Apenas verifica se o notebook existe, sem carregar o objeto inteiro.
    notebook_localizacao = db.session.query(Notebook.localizacao).filter_by(id=notebook_id).scalar()
    if notebook_localizacao is None:
        flash('Ativo não encontrado!', 'error')
        return redirect(url_for('inventory.inventario'))

    if request.method == 'POST':
        categoria = request.form.get('categoria', 'OUTROS').strip().upper()
        prioridade = request.form.get('prioridade', 'Normal').strip()
        tipo_problema = request.form['tipo_problema'].strip().upper()
        descricao = request.form['descricao'].strip().upper()
        local_incidente = request.form.get('local_incidente', notebook_localizacao).strip().upper()
        responsavel = session.get('username', 'Sistema')

        novo_problema = Problema(
            notebook_id=notebook_id, local_incidente=local_incidente, categoria=categoria,
            prioridade=prioridade, tipo_problema=tipo_problema, descricao=descricao,
            responsavel=responsavel, status='Aberto'
        )
        db.session.add(novo_problema)

        # Atualiza o status diretamente no banco
        Notebook.query.filter_by(id=notebook_id).update({'status': 'Em manutenção'})
        db.session.commit()

        flash('Chamado aberto com sucesso!<br><br>A equipe de TI foi notificada e o status do equipamento foi atualizado.', 'success')
        if request.args.get('kiosk'):
            return redirect(url_for('maintenance.nova_manutencao', kiosk=1))
        return redirect(url_for('inventory.historico', notebook_id=notebook_id))

    return render_template('reportar_problema.html', notebook={'id': notebook_id, 'localizacao': notebook_localizacao})

@maintenance_bp.route('/problemas/<int:problema_id>/resolver', methods=['POST'])
@permission_required('perm_chamados')
def resolver_problema(problema_id):
    problema = db.session.get(Problema, problema_id) # MODERNIZADO
    if not problema:
        flash('Chamado não encontrado!', 'error')
        return redirect(url_for('maintenance.problemas'))

    parecer = request.form.get('parecer_tecnico', 'Resolvido sem parecer detalhado.').strip().upper()
    problema.status = 'Resolvido'
    problema.parecer_tecnico = parecer 
    problema.data_resolucao = datetime.now()
    
    # CORREÇÃO: Como a 'relationship' foi removida, usamos o notebook_id diretamente.
    if problema.notebook_id:
        obs = f"Chamado #{problema_id} resolvido. Parecer: {parecer}"
        novo_historico = Historico(id_etiqueta=problema.notebook_id, acao='Manutenção Concluída', usuario_movimentacao=session.get('username', 'Sistema'), responsavel='-', obs=obs)
        db.session.add(novo_historico)
        Notebook.query.filter_by(id=problema.notebook_id).update({'status': 'Disponível'})
        flash('Chamado resolvido e ativo liberado.', 'success')
    else:
        flash('Chamado resolvido com sucesso.', 'success')
        
    db.session.commit()
    return redirect(url_for('maintenance.problemas'))

@maintenance_bp.route('/manutencao/historico')
@permission_required('perm_chamados')
def historico_chamados():
    if not request.args:
        data_inicio = datetime.now().strftime('%Y-%m-%d')
        data_fim = datetime.now().strftime('%Y-%m-%d')
    else:
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')
    
    query = db.session.query(
        Problema, 
        Notebook.numero_carrinho
    ).outerjoin(Notebook, Problema.notebook_id == Notebook.id)
    
    if data_inicio:
        query = query.filter(Problema.data_registro >= datetime.strptime(f"{data_inicio} 00:00:00", '%Y-%m-%d %H:%M:%S'))
    if data_fim:
        query = query.filter(Problema.data_registro <= datetime.strptime(f"{data_fim} 23:59:59", '%Y-%m-%d %H:%M:%S'))
        
    chamados_brutos = query.order_by(Problema.data_registro.desc()).all()
    
    chamados_processados = []
    for row in chamados_brutos:
        problema = row.Problema
        problema.numero_carrinho = row.numero_carrinho # CORREÇÃO: Atribui o numero_carrinho ao objeto problema
        problema.data_formatada = problema.data_registro.strftime('%d/%m/%Y %H:%M') if problema.data_registro else ''
        
        tempo_str = "-"
        
        if problema.data_resolucao and problema.data_registro:
            try:
                # Agora são objetos datetime, o cálculo é direto
                diff = problema.data_resolucao - problema.data_registro
                
                horas = int(diff.total_seconds() // 3600)
                minutos = int((diff.total_seconds() % 3600) // 60)
                
                tempo_str = f"{horas}h {minutos}m" if horas > 0 else f"{minutos}m"
            except Exception:
                pass
                
        problema.tempo_atendimento = tempo_str
        chamados_processados.append(problema)
        
    return render_template('historico_chamados.html', problemas=chamados_processados, data_inicio=data_inicio, data_fim=data_fim)
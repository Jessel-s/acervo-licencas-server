from flask import Blueprint, current_app, render_template, request, redirect, url_for, flash, session, send_file
from datetime import datetime
import base64
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
import os
import sys
import pandas as pd
from sqlalchemy import exc, func, or_

from models import db, Ativo, Historico, Problema
from auth import login_required, permission_required
from sync_queue import enqueue_asset, enqueue_history

inventory_bp = Blueprint('inventory', __name__)

if getattr(sys, 'frozen', False):
    basedir = os.path.dirname(sys.executable)
else:
    basedir = os.path.abspath(os.path.dirname(__file__))


def _queue_asset_sync(asset, operation='upsert'):
    try:
        enqueue_asset(asset, operation, os.path.join(basedir, 'sync_queue.db'))
    except Exception:
        current_app.logger.exception('Falha ao registrar sincronizacao pendente do ativo %s.', asset.id)


def _queue_history_sync(record):
    try:
        enqueue_history(record, os.path.join(basedir, 'sync_queue.db'))
    except Exception:
        current_app.logger.exception('Falha ao registrar sincronizacao pendente do historico %s.', record.id)

def _create_qr_label_image(notebook_id, size='d110'):
    notebook = db.session.get(Ativo, notebook_id) # MODERNIZADO
    titulo_etiqueta = notebook.tipo.upper() if notebook and notebook.tipo else notebook_id

    # Presets para diferentes tamanhos de etiqueta
    presets = {
        'd110':   {'qr_box': 4, 'font_id': 50, 'font_titulo': 16, 'padding': 4, 'orientation': 'vertical'},
        '50x30':  {'qr_box': 5, 'font_id': 28, 'font_titulo': 20, 'padding': 10, 'orientation': 'vertical'},
        '30x20':  {'qr_box': 3, 'font_id': 22, 'font_titulo': 14, 'padding': 5, 'orientation': 'vertical'}
    }
    config = presets.get(size, presets['d110'])

    qr_box_size = config['qr_box']
    font_size_id = config['font_id']
    font_size_titulo = config['font_titulo']
    padding = config['padding']
    orientation = config['orientation']

    # --- MUDANÇA CRÍTICA: USA O IP NUMÉRICO DA REDE ---
    # Celulares não resolvem nomes Windows nativamente via Wi-Fi. O IP resolve isso.
    from utils import obter_ip_local
    from flask import request
    
    meu_ip = obter_ip_local()
        
    qr_data = f"https://{meu_ip}:8080/ativo/{notebook_id}"
    
    # UPGRADE EMPRESARIAL: Tolerância a Danos (Error Correction Q = 25% de restauração)
    # Garante que mesmo que a etiqueta risque, rasgue ou suje, o leitor USB ainda consiga ler.
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=qr_box_size, border=1)
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert('RGB')
    qr_width, qr_height = qr_img.size

    try:
        font_id = ImageFont.truetype(os.path.join(basedir, "arialbd.ttf"), font_size_id)
        font_titulo = ImageFont.truetype(os.path.join(basedir, "arialbd.ttf"), font_size_titulo)
    except IOError:
        font_id = ImageFont.load_default()
        font_titulo = ImageFont.load_default()

    bbox_titulo = font_titulo.getbbox(titulo_etiqueta)
    w_titulo, h_titulo = bbox_titulo[2] - bbox_titulo[0], bbox_titulo[3] - bbox_titulo[1]
    
    bbox_id = font_id.getbbox(notebook_id)
    w_id, h_id = bbox_id[2] - bbox_id[0], bbox_id[3] - bbox_id[1]

    if orientation == 'vertical':
        titulo_img = Image.new('RGB', (w_titulo + 2, h_titulo + 2), 'white')
        titulo_draw = ImageDraw.Draw(titulo_img)
        titulo_draw.text(((w_titulo + 2) / 2, (h_titulo + 2) / 2), titulo_etiqueta, font=font_titulo, fill="black", anchor="mm")
        rotated_titulo_img = titulo_img.rotate(90, expand=True)
        rw_titulo, rh_titulo = rotated_titulo_img.size

        id_img = Image.new('RGB', (w_id + 10, h_id + 10), 'white')
        id_draw = ImageDraw.Draw(id_img)
        id_draw.text(((w_id + 10) / 2, (h_id + 10) / 2), notebook_id, font=font_id, fill="black", anchor="mm")
        rotated_id_img = id_img.rotate(90, expand=True)
        rw_id, rh_id = rotated_id_img.size

        canvas_height = max(rh_titulo, qr_height, rh_id) + (padding * 2)
        canvas_width = rw_titulo + qr_width + rw_id + (padding * 4)

        final_img = Image.new('RGB', (canvas_width, canvas_height), 'white')

        x_titulo = padding
        y_titulo = (canvas_height - rh_titulo) // 2
        final_img.paste(rotated_titulo_img, (x_titulo, y_titulo))

        x_qr = rw_titulo + (padding * 2)
        y_qr = (canvas_height - qr_height) // 2
        final_img.paste(qr_img, (x_qr, y_qr))

        x_id = x_qr + qr_width + padding
        y_id = (canvas_height - rh_id) // 2
        final_img.paste(rotated_id_img, (x_id, y_id))
    else: # Horizontal
        canvas_width = qr_width + max(w_titulo, w_id) + (padding * 3)
        canvas_height = max(qr_height, h_titulo + h_id + padding) + (padding * 2)
        final_img = Image.new('RGB', (canvas_width, canvas_height), 'white')
        draw = ImageDraw.Draw(final_img)

        # QR Code à esquerda
        y_qr = (canvas_height - qr_height) // 2
        final_img.paste(qr_img, (padding, y_qr))

        # Textos à direita (Empilhados)
        x_text = qr_width + (padding * 2)
        y_text_start = (canvas_height - (h_titulo + h_id + padding)) // 2
        draw.text((x_text, y_text_start), titulo_etiqueta, font=font_titulo, fill="black")
        draw.text((x_text, y_text_start + h_titulo + padding), notebook_id, font=font_id, fill="black")
    
    return final_img

@inventory_bp.route('/inventario')
@login_required
def inventario():
    # Captura os filtros digitados pelo usuário
    patrimonio_filtro = request.args.get('patrimonio', '').strip().upper()
    status_filtro = request.args.get('status', '').strip()
    
    # CORREÇÃO DEFINITIVA: Em vez de carregar o objeto Ativo inteiro (o que causa o erro de conversão de data),
    # selecionamos explicitamente apenas as colunas necessárias para a tabela do inventário.
    # Isso impede que o SQLAlchemy tente converter colunas de data que possam estar corrompidas no banco.
    query = db.session.query(Ativo).with_entities(
        Ativo.id, Ativo.tipo, Ativo.modelo, Ativo.numero_serie,
        Ativo.localizacao, Ativo.status
    )
    
    if patrimonio_filtro:
        query = query.filter(Ativo.id.like(f"%{patrimonio_filtro}%"))
        
    if status_filtro:
        query = query.filter(Ativo.status == status_filtro)

    # O resultado da query já é uma lista de objetos que se comportam como dicionários.
    notebooks = query.order_by(Ativo.id).all()
    
    return render_template('inventario.html', notebooks=notebooks, filtro_patrimonio=patrimonio_filtro, filtro_status=status_filtro)

@inventory_bp.route('/cadastro', methods=('GET', 'POST'))
@permission_required('perm_cadastro')
def cadastro():
    if request.method == 'POST':
        idn_raw = request.form['id'].strip()
        if not idn_raw.isdigit():
            flash('Erro: O Patrimônio deve conter apenas números!', 'error')
            return redirect(url_for('inventory.cadastro'))
            
        idn = idn_raw.zfill(5)
        tipo = request.form.get('tipo', 'EQUIPAMENTO').strip().upper()
        numero_carrinho = request.form.get('numero_carrinho', '').strip()
        numero_carrinho = int(numero_carrinho) if numero_carrinho.isdigit() else None
        modelo = request.form['modelo'].strip().upper()
        numero_serie = request.form.get('numero_serie', '').strip().upper()
        data_compra = request.form.get('data_compra', '').strip()
        localizacao = request.form.get('localizacao', '').strip().upper()
        observacoes = request.form.get('observacoes', '').strip().upper()
        
        try:
            novo_notebook = Ativo(
                id=idn,
                tipo=tipo, 
                numero_carrinho=numero_carrinho, 
                modelo=modelo,
                numero_serie=numero_serie,
                data_compra=data_compra,
                status='Disponível',
                localizacao=localizacao,
                observacoes=observacoes
            )
            db.session.add(novo_notebook)

            obs = f"{tipo} ID '{idn}' (Nº {numero_carrinho or 'N/A'}) cadastrado."
            novo_historico = Historico(id_etiqueta=idn, acao='Cadastro', usuario_movimentacao=session.get('username', 'Sistema'), obs=obs)
            db.session.add(novo_historico)
            
            db.session.commit()
            _queue_asset_sync(novo_notebook)
            _queue_history_sync(novo_historico)
            flash('Ativo cadastrado com sucesso!', 'success')
        except exc.IntegrityError as e:
            db.session.rollback()
            if 'UNIQUE constraint failed: notebooks.id' in str(e):
                flash(f'Erro: O Patrimônio/ID "{idn}" já está cadastrado!', 'error')
            elif 'UNIQUE constraint failed: notebooks.numero_carrinho' in str(e):
                flash(f'Erro: O Número "{numero_carrinho}" já pertence a outro equipamento! Este número deve ser único (Ex: posição 1, 2, 3...).', 'error')
            else:
                flash(f'Erro ao cadastrar: Dados duplicados ou inválidos. Detalhe: {e}', 'error')
            
    atual_max = db.session.query(db.func.max(Ativo.numero_carrinho)).scalar()
    sugestao_controle = (atual_max + 1) if atual_max else 1

    return render_template('cadastro.html', sugestao_controle=sugestao_controle)

@inventory_bp.route('/editar/<string:notebook_id>', methods=('GET', 'POST'))
@permission_required('perm_cadastro')
def editar(notebook_id):
    if notebook_id.isdigit():
        notebook_id = notebook_id.zfill(5) # MODERNIZADO
    notebook = db.session.get(Ativo, notebook_id)

    if not notebook:
        flash('Ativo não encontrado!', 'error')
        return redirect(url_for('inventory.inventario'))

    if request.method == 'POST':
        novo_numero_carrinho = request.form.get('numero_carrinho', '').strip()
        novo_numero_carrinho = int(novo_numero_carrinho) if novo_numero_carrinho.isdigit() else None
        novo_tipo = request.form.get('tipo', 'EQUIPAMENTO').strip().upper()
        novo_modelo = request.form['modelo'].strip().upper()
        novo_numero_serie = request.form.get('numero_serie', '').strip().upper()
        nova_data_compra = request.form.get('data_compra', '').strip()
        nova_localizacao = request.form.get('localizacao', '').strip().upper()
        novas_observacoes = request.form.get('observacoes', '').strip().upper()

        try:
            notebook.numero_carrinho = novo_numero_carrinho
            notebook.tipo = novo_tipo
            notebook.modelo = novo_modelo
            notebook.numero_serie = novo_numero_serie
            notebook.data_compra = nova_data_compra
            notebook.localizacao = nova_localizacao
            notebook.observacoes = novas_observacoes

            obs = f"Informações do ativo ID '{notebook_id}' atualizadas."
            novo_historico = Historico(id_etiqueta=notebook_id, acao='Edição', usuario_movimentacao=session.get('username', 'Sistema'), obs=obs)
            db.session.add(novo_historico)
            db.session.commit()
            _queue_asset_sync(notebook)
            _queue_history_sync(novo_historico)
            flash('Ativo atualizado com sucesso!', 'success')
        except exc.IntegrityError:
            db.session.rollback()
            flash(f'Erro: O número de controle "{novo_numero_carrinho}" já está em uso por outro equipamento.', 'error')
            return redirect(url_for('inventory.editar', notebook_id=notebook_id))
        return redirect(url_for('inventory.inventario'))

    return render_template('editar.html', notebook=notebook)

@inventory_bp.route('/remover/<string:notebook_id>', methods=['POST'])
@permission_required('perm_cadastro')
def remover(notebook_id):
    # BLINDAGEM DE SEGURANÇA: Apenas administradores (com perm_config) podem excluir equipamentos
    if not session.get('perm_config'):
        flash('Acesso Negado: Apenas Administradores podem excluir ativos. Se o equipamento não for mais usado, mude seu status para "Inativo" editando-o.', 'error')
        return redirect(url_for('inventory.inventario'))
        
    if notebook_id.isdigit():
        notebook_id = notebook_id.zfill(5) # MODERNIZADO
    notebook = db.session.get(Ativo, notebook_id)

    if notebook:
        db.session.delete(notebook)
        db.session.commit()
        _queue_asset_sync(notebook, 'delete')
        flash(f'Ativo {notebook_id} e todo o seu histórico foram removidos permanentemente!', 'success')
    else:
        flash('Erro: O ativo não foi encontrado.', 'error')
    return redirect(url_for('inventory.inventario'))

@inventory_bp.route('/gerar_qr', methods=['POST'])
@permission_required('perm_cadastro')
def gerar_qr():
    selected_ids = request.form.getlist('selected_ids')
    label_size = request.form.get('label_size', 'd110')
    page_sizes = {
        'd110': '40mm 30mm',
        '50x30': '50mm 30mm',
        '30x20': '30mm 20mm'
    }
    qr_codes_data = []
    for notebook_id in selected_ids:
        final_img = _create_qr_label_image(notebook_id, label_size)
        buffered = io.BytesIO()
        final_img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
        qr_codes_data.append({'id': notebook_id, 'image': f"data:image/png;base64,{img_str}"})
    return render_template(
        'gerar_qr.html',
        qr_codes=qr_codes_data,
        label_size=label_size,
        page_size=page_sizes.get(label_size, page_sizes['d110'])
    )

@inventory_bp.route('/download_qr/<string:notebook_id>')
@permission_required('perm_cadastro')
def download_qr(notebook_id):
    label_size = request.args.get('label_size', 'd110')
    final_img = _create_qr_label_image(notebook_id, label_size)
    img_io = io.BytesIO()
    final_img.save(img_io, 'PNG')
    img_io.seek(0)
    return send_file(img_io, as_attachment=True, download_name=f'qrcode_{notebook_id}.png', mimetype='image/png')

@inventory_bp.route('/importar', methods=('GET', 'POST'))
@permission_required('perm_cadastro')
def importar():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo enviado.', 'error')
            return redirect(url_for('inventory.importar'))
        
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'error')
            return redirect(url_for('inventory.importar'))
            
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Por favor, envie um arquivo Excel (.xlsx ou .xls).', 'error')
            return redirect(url_for('inventory.importar'))
            
        try:
            df = pd.read_excel(file)
            df.columns = [str(c).strip().upper() for c in df.columns]
            
            if 'ID_PATRIMONIO' not in df.columns or 'MODELO' not in df.columns:
                flash('ERRO: O Excel deve conter no mínimo as colunas "ID_PATRIMONIO" e "MODELO". Baixe a planilha de exemplo.', 'error')
                return redirect(url_for('inventory.importar'))
            
            # Força a coluna para numérico (ignora textos como 'EQ-01') e remove os vazios
            df['ID_PATRIMONIO'] = pd.to_numeric(df['ID_PATRIMONIO'], errors='coerce')
            df = df.dropna(subset=['ID_PATRIMONIO'])
            
            if df.empty:
                flash('A planilha está vazia ou os IDs não são números válidos.', 'error')
                return redirect(url_for('inventory.importar'))
            
            # Remove duplicados DENTRO da própria planilha de Excel antes de tentar salvar
            df = df.drop_duplicates(subset=['ID_PATRIMONIO'])
            
            # Formata para inteiro e preenche com zeros (Ex: 1 -> '00001')
            df['ID_PATRIMONIO'] = df['ID_PATRIMONIO'].astype(int).astype(str).str.zfill(5)
            ids_planilha = df['ID_PATRIMONIO'].tolist()
            
            existentes_query = db.session.query(Ativo.id).filter(Ativo.id.in_(ids_planilha)).all()
            existentes = [row.id for row in existentes_query]
            
            if existentes:
                flash(f'BLOQUEIO: Os seguintes equipamentos já existem no sistema: {", ".join(existentes)}. Remova-os da planilha ou continue a numeração a partir de novos IDs.', 'error')
                return redirect(url_for('inventory.importar'))
            
            usuario = session.get('username', 'Sistema')
            
            cadastrados = 0
            ativos_importados = []
            historicos_importados = []
            
            atual_max = db.session.query(db.func.max(Ativo.numero_carrinho)).scalar()
            prox_carrinho = (atual_max + 1) if atual_max else 1
            
            for index, row in df.iterrows():
                idn = str(row['ID_PATRIMONIO']).strip().upper()
                if pd.isna(row['ID_PATRIMONIO']) or not idn or idn == 'NAN': continue
                    
                tipo = str(row.get('TIPO', 'EQUIPAMENTO')).strip().upper() if pd.notna(row.get('TIPO')) else 'EQUIPAMENTO'
                modelo = str(row.get('MODELO', '')).strip().upper() if pd.notna(row.get('MODELO')) else 'NÃO INFORMADO'
                numero_serie = str(row.get('NUMERO_SERIE', '')).strip().upper() if pd.notna(row.get('NUMERO_SERIE')) else ''
                data_compra = str(row.get('DATA_COMPRA', '')).strip() if pd.notna(row.get('DATA_COMPRA')) else ''
                localizacao = str(row.get('LOCALIZACAO', '')).strip().upper() if pd.notna(row.get('LOCALIZACAO')) else ''
                observacoes = str(row.get('OBSERVACOES', '')).strip().upper() if pd.notna(row.get('OBSERVACOES')) else ''
                
                novo_notebook = Ativo(
                    id=idn, tipo=tipo, numero_carrinho=prox_carrinho, modelo=modelo,
                    numero_serie=numero_serie, data_compra=data_compra, status='Disponível',
                    localizacao=localizacao, observacoes=observacoes
                )
                db.session.add(novo_notebook)
                ativos_importados.append(novo_notebook)
                
                obs = f"Importação em lote (Excel). {tipo} adicionado."
                novo_historico = Historico(
                    id_etiqueta=idn, acao='Cadastro', usuario_movimentacao=usuario, 
                    responsavel='-', obs=obs
                )
                db.session.add(novo_historico)
                historicos_importados.append(novo_historico)
                
                cadastrados += 1
                prox_carrinho += 1
            
            db.session.commit()
            for ativo in ativos_importados:
                _queue_asset_sync(ativo)
            for historico in historicos_importados:
                _queue_history_sync(historico)
            flash(f'Importação concluída com Sucesso! {cadastrados} equipamentos adicionados ao sistema.', 'success')
            return redirect(url_for('inventory.inventario'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao processar o arquivo Excel: Verifique os dados e tente novamente. (Erro técnico: {str(e)})', 'error')
            return redirect(url_for('inventory.importar'))
            
    return render_template('importar.html')

@inventory_bp.route('/download_template_excel')
@permission_required('perm_cadastro')
def download_template_excel():
    output = io.BytesIO()
    df = pd.DataFrame(columns=['ID_PATRIMONIO', 'TIPO', 'MODELO', 'NUMERO_SERIE', 'DATA_COMPRA', 'LOCALIZACAO', 'OBSERVACOES'])
    df.loc[0] = ['00001', 'NOTEBOOK', 'DELL INSPIRON', 'CN28913BR', '2024-01-15', 'ESTOQUE PRINCIPAL', 'COMPRA LOTE 2024']
    df.loc[1] = ['00002', 'TABLET', 'SAMSUNG GALAXY S6', '', '', 'ESTOQUE PRINCIPAL', '']
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template_Importacao')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='modelo_importacao.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@inventory_bp.route('/historico/<string:notebook_id>')
@login_required
def historico(notebook_id):
    if notebook_id.isdigit():
        notebook_id = notebook_id.zfill(5)
    notebook = db.session.get(Ativo, notebook_id)
    if not notebook:
        flash('Ativo não encontrado!', 'error')
        return redirect(url_for('inventory.inventario'))

    problem_history_raw = []
    if session.get('perm_chamados'):
        problem_history_raw = Problema.query.filter_by(notebook_id=notebook_id).order_by(Problema.data_registro.desc()).all()

    # Process problem_history to safely format dates
    problem_history = []
    for prob in problem_history_raw:
        # CORREÇÃO: Constrói o dicionário manualmente em vez de usar _asdict()
        prob_dict = {
            'id': prob.id,
            'notebook_id': prob.notebook_id,
            'tipo_problema': prob.tipo_problema,
            'descricao': prob.descricao,
            'responsavel': prob.responsavel,
            'status': prob.status,
            'prioridade': prob.prioridade,
            'categoria': prob.categoria,
            'parecer_tecnico': prob.parecer_tecnico,
            'local_incidente': prob.local_incidente
        }
        data_raw = prob.data_registro
        prob_dict['formatted_data_registro'] = ''
        if data_raw:
            try:
                # Converte para string primeiro para lidar com inteiros ou outros tipos
                data_obj = datetime.fromisoformat(str(data_raw)) 
                prob_dict['formatted_data_registro'] = data_obj.strftime('%d/%m/%Y %H:%M')
            except (ValueError, TypeError):
                prob_dict['formatted_data_registro'] = str(data_raw) # Fallback to raw string
        problem_history.append(prob_dict)

    # OTIMIZAÇÃO: Seleciona apenas as colunas necessárias para o histórico geral,
    # tornando a consulta mais leve e evitando carregar o objeto inteiro.
    general_history_query = db.session.query(Historico).with_entities(
        Historico.acao, Historico.data, Historico.usuario_movimentacao, Historico.responsavel, Historico.obs
    ).filter_by(id_etiqueta=notebook_id).order_by(Historico.data.desc()).all()

    # Process general_history to safely format dates
    general_history = []
    for log in general_history_query:
        # CORREÇÃO: ._asdict() funciona aqui porque a query usa .with_entities(), que retorna namedtuples
        # No entanto, para consistência e robustez, vamos construir o dicionário manualmente.
        log_dict = {
            'acao': log.acao,
            'data': log.data,
            'usuario_movimentacao': log.usuario_movimentacao,
            'responsavel': log.responsavel,
            'obs': log.obs
        }
        data_raw = log.data
        log_dict['formatted_data'] = ''
        if data_raw:
            try:
                data_obj = datetime.fromisoformat(str(data_raw))
                log_dict['formatted_data'] = data_obj.strftime('%d/%m/%Y %H:%M')
            except (ValueError, TypeError):
                log_dict['formatted_data'] = str(data_raw) # Fallback to raw string
        general_history.append(log_dict)

    # CORREÇÃO DEFINITIVA: Formata data_cadastro para exibição no template de forma segura, lidando com int, str, ou None.
    formatted_data_cadastro = 'N/A'
    if notebook.data_cadastro:
        try:
            # Tenta converter a string ISO para datetime e formatar
            formatted_data_cadastro = datetime.fromisoformat(str(notebook.data_cadastro)).strftime('%d/%m/%Y %H:%M')
        except (ValueError, TypeError):
            # Se a conversão falhar (ex: é um inteiro, ou uma string mal formatada), apenas exibe o valor como está.
            formatted_data_cadastro = str(notebook.data_cadastro)

    return render_template('historico.html', notebook=notebook, problem_history=problem_history, general_history=general_history, formatted_data_cadastro=formatted_data_cadastro)

@inventory_bp.route('/historico_geral')
@permission_required('perm_cadastro')
def historico_geral():
    if not request.args:
        data_inicio = datetime.now().strftime('%Y-%m-%d')
        data_fim = datetime.now().strftime('%Y-%m-%d')
    else:
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')

    acao_filtro = request.args.get('acao', '')
    busca = request.args.get('busca', '').strip()
    
    query = Historico.query.filter(Historico.acao != 'Manutenção Concluída')
    
    if data_inicio:
        try:
            dt_inicio_obj = datetime.strptime(f"{data_inicio} 00:00:00", '%Y-%m-%d %H:%M:%S')
            query = query.filter(Historico.data >= dt_inicio_obj)
        except ValueError: pass # Ignora data inválida
    if data_fim:
        try:
            dt_fim_obj = datetime.strptime(f"{data_fim} 23:59:59", '%Y-%m-%d %H:%M:%S')
            query = query.filter(Historico.data <= dt_fim_obj.isoformat())
        except ValueError: pass # Ignora data inválida
    if acao_filtro: query = query.filter(Historico.acao == acao_filtro)
    if busca:
        busca_like = f'%{busca}%'
        query = query.filter(or_(Historico.id_etiqueta.like(busca_like), Historico.usuario_movimentacao.like(busca_like), Historico.obs.like(busca_like)))
        
    history_records = query.order_by(Historico.data.desc()).all()
    acoes_db = [row.acao for row in db.session.query(Historico.acao).filter(Historico.acao != 'Manutenção Concluída').distinct().order_by(Historico.acao)]
    
    return render_template('historico_geral.html', history=history_records, data_inicio=data_inicio, data_fim=data_fim, filtro_acao=acao_filtro, filtro_busca=busca, acoes=acoes_db)

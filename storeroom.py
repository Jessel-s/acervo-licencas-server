from flask import Blueprint, current_app, render_template, request, jsonify, redirect, url_for, session, flash, g, send_file
from datetime import datetime
from functools import wraps
from sqlalchemy import func
import qrcode
import base64
import io
import os
import pandas as pd
from PIL import Image, ImageDraw, ImageFont # Importação mantida, mesmo que não usada neste diff
from models import db, AlmoxProduto, AlmoxMovimentacao
from auth import login_required, permission_required
from sync_queue import enqueue_storeroom_movement, enqueue_storeroom_product

storeroom_bp = Blueprint('storeroom', __name__, url_prefix='/almoxarifado')


def _queue_product_sync(product, operation='upsert'):
    try:
        enqueue_storeroom_product(product, operation)
    except Exception:
        current_app.logger.exception('Falha ao registrar sincronizacao pendente do produto %s.', product.id)


def _queue_movement_sync(movement, operation='upsert'):
    try:
        enqueue_storeroom_movement(movement, operation)
    except Exception:
        current_app.logger.exception('Falha ao registrar sincronizacao pendente da movimentacao %s.', movement.id)

@storeroom_bp.route('/')
@login_required
@permission_required('perm_almoxarifado')
def dashboard():
    """Painel principal do Almoxarifado."""
    # Resumo Rápido
    total_itens = db.session.query(db.func.sum(AlmoxProduto.quantidade_atual)).scalar() or 0
    itens_baixo_estoque = AlmoxProduto.query.filter(AlmoxProduto.quantidade_atual <= AlmoxProduto.estoque_minimo).count()
    total_skus = AlmoxProduto.query.count()
    
    # Produtos em Baixo Estoque (Alerta Vermelho)
    alertas_estoque = AlmoxProduto.query.filter(AlmoxProduto.quantidade_atual <= AlmoxProduto.estoque_minimo).order_by(AlmoxProduto.quantidade_atual.asc()).all()
    
    # Movimentações Recentes
    # CORREÇÃO: Explicitamente seleciona as colunas e trata data_movimentacao como texto
    # para evitar ValueError se houver dados corrompidos.
    from sqlalchemy import cast, Text # Importação já existe no arquivo
    movimentacoes = db.session.query(
        AlmoxMovimentacao.tipo, AlmoxMovimentacao.quantidade, AlmoxMovimentacao.usuario,
        AlmoxMovimentacao.destino_id, AlmoxMovimentacao.observacao, AlmoxMovimentacao.data_movimentacao, # Inclui data_movimentacao original
        AlmoxProduto.nome, AlmoxProduto.sku,
        cast(AlmoxMovimentacao.data_movimentacao, Text).label('data_movimentacao_raw') # Lê como texto
    ).join(AlmoxProduto, AlmoxMovimentacao.produto_id == AlmoxProduto.id).order_by(AlmoxMovimentacao.id.desc()).limit(10).all()

    # Produtos para o Autocomplete
    produtos = AlmoxProduto.query.order_by(AlmoxProduto.nome.asc()).all()

    return render_template('storeroom/dashboard.html', 
                           total_itens=total_itens, 
                           itens_baixo_estoque=itens_baixo_estoque, 
                           total_skus=total_skus,
                           alertas_estoque=alertas_estoque, # Esta é uma lista de objetos AlmoxProduto, está correto.
                           movimentacoes=[
                               {
                                   'tipo': m.tipo, 'quantidade': m.quantidade, 'usuario': m.usuario,
                                   'destino_id': m.destino_id, 'observacao': m.observacao,
                                    'nome': m.nome, 'sku': m.sku,
                                   # Tenta formatar a data, ignorando se for inválida (ex: '7') ou se não for datetime
                                   'data_formatada': datetime.fromisoformat(m.data_movimentacao_raw).strftime('%d/%m/%Y %H:%M')
                                   if m.data_movimentacao_raw and '20' in m.data_movimentacao_raw else ''
                               }
                               for m in movimentacoes
                           ],
                           produtos=produtos)

@storeroom_bp.route('/produtos')
@login_required
@permission_required('perm_almoxarifado')
def listar_produtos():
    """Lista todos os produtos do Almoxarifado."""
    busca = request.args.get('busca', '').strip()
    categoria = request.args.get('categoria', '')
    
    query = AlmoxProduto.query
    
    if busca:
        busca_like = f"%{busca}%"
        query = query.filter(db.or_(AlmoxProduto.sku.like(busca_like), AlmoxProduto.nome.like(busca_like)))
        
    if categoria:
        query = query.filter(AlmoxProduto.categoria == categoria)
        
    produtos = query.order_by(AlmoxProduto.nome.asc()).all()
    
    categorias_query = db.session.query(AlmoxProduto.categoria).filter(AlmoxProduto.categoria != None, AlmoxProduto.categoria != '').distinct().order_by(AlmoxProduto.categoria)
    categorias = [row.categoria for row in categorias_query]
    
    return render_template('storeroom/produtos.html', produtos=produtos, filtro_busca=busca, filtro_categoria=categoria, categorias=categorias)

@storeroom_bp.route('/produtos/novo', methods=['POST'])
@login_required
@permission_required('perm_almoxarifado')
def novo_produto():
    """Cadastra um novo produto."""
    sku = request.form.get('sku', '').strip().upper()
    nome = request.form.get('nome', '').strip().upper()
    categoria = request.form.get('categoria', '').strip()
    estoque_minimo = request.form.get('estoque_minimo', 5, type=int)
    custo_unitario = request.form.get('custo_unitario', 0.0, type=float)
    quantidade_inicial = request.form.get('quantidade_inicial', 0, type=int)
    
    if not sku or not nome:
        flash('SKU e Nome são obrigatórios!', 'danger')
        return redirect(url_for('storeroom.listar_produtos'))
        
    try:
        novo_produto = AlmoxProduto(
            sku=sku, nome=nome, categoria=categoria, quantidade_atual=quantidade_inicial,
            estoque_minimo=estoque_minimo, custo_unitario=custo_unitario
        )
        db.session.add(novo_produto)
        db.session.flush() # Para obter o ID do novo produto antes do commit
        
        if quantidade_inicial > 0:
            nova_movimentacao = AlmoxMovimentacao(
                produto_id=novo_produto.id, tipo='ENTRADA', quantidade=quantidade_inicial,
                usuario=session.get('username', 'Sistema'), destino_id='Estoque Inicial',
                observacao='Entrada Inicial'
            )
            db.session.add(nova_movimentacao)
            
        db.session.commit()
        _queue_product_sync(novo_produto)
        if quantidade_inicial > 0:
            _queue_movement_sync(nova_movimentacao)
        flash(f'Produto {nome} cadastrado com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao cadastrar: Já existe um produto com o SKU {sku}.', 'danger')
        
    return redirect(url_for('storeroom.listar_produtos'))

@storeroom_bp.route('/produtos/editar/<int:id>', methods=['POST'])
@login_required
@permission_required('perm_almoxarifado')
def editar_produto(id):
    """Edita um produto existente."""
    nome = request.form.get('nome', '').strip().upper()
    categoria = request.form.get('categoria', '').strip()
    estoque_minimo = request.form.get('estoque_minimo', 5, type=int)
    
    if not nome:
        flash('O nome do produto é obrigatório!', 'danger')
        return redirect(url_for('storeroom.listar_produtos'))
        
    produto = db.session.get(AlmoxProduto, id) # MODERNIZADO
    if produto:
        produto.nome = nome
        produto.categoria = categoria
        produto.estoque_minimo = estoque_minimo
        db.session.commit()
        _queue_product_sync(produto)
    flash(f'Produto atualizado com sucesso!', 'success')
    return redirect(url_for('storeroom.listar_produtos'))

@storeroom_bp.route('/produtos/remover/<int:id>', methods=['POST'])
@login_required
@permission_required('perm_almoxarifado')
def remover_produto(id):
    """Remove um produto e seu histórico de movimentações."""
    produto = db.session.get(AlmoxProduto, id) # MODERNIZADO
    if produto:
        produto_id = produto.id
        movimentacoes = AlmoxMovimentacao.query.filter_by(produto_id=id).all()
        # O SQLAlchemy cuidará da remoção em cascata se configurado, mas é mais seguro fazer manualmente para SQLite
        AlmoxMovimentacao.query.filter_by(produto_id=id).delete()
        db.session.delete(produto)
        db.session.commit()
        for movimentacao in movimentacoes:
            _queue_movement_sync(movimentacao, 'delete')
        class RemovedProduct:
            id = produto_id
        _queue_product_sync(RemovedProduct(), 'delete')
        flash('Produto removido com sucesso!', 'success')
    else:
        flash('Produto não encontrado.', 'danger')
        
    return redirect(url_for('storeroom.listar_produtos'))

@storeroom_bp.route('/movimentar', methods=['POST'])
@login_required
@permission_required('perm_almoxarifado')
def movimentar_estoque():
    """Registra Entrada ou Saída de um produto."""
    produto_id = request.form.get('produto_id', type=int)
    busca_sku = request.form.get('busca_produto', '').strip().upper()
    tipo = request.form.get('tipo', '').upper() # 'ENTRADA' ou 'SAIDA'
    quantidade = request.form.get('quantidade', 1, type=int)
    destino_id = request.form.get('destino_id', '').strip()
    observacao = request.form.get('observacao', '').strip()
    
    # Suporte a Leitor de QR Code: se não preencheu o ID via Autocomplete, tenta buscar pelo SKU exato
    if not produto_id and busca_sku:
        prod = AlmoxProduto.query.filter_by(sku=busca_sku).first()
        if prod:
            produto_id = prod.id
            
    if not produto_id or not tipo or quantidade <= 0:
        flash('Produto não encontrado ou dados inválidos.', 'danger')
        return redirect(url_for('storeroom.dashboard'))
    
    # Verifica estoque atual
    produto = db.session.get(AlmoxProduto, produto_id) # MODERNIZADO
    if not produto:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('storeroom.dashboard'))
        
    quantidade_atual = produto.quantidade_atual
    
    if tipo == 'SAIDA' and quantidade > quantidade_atual:
        flash(f'Estoque insuficiente de {produto.nome}. Possui apenas {quantidade_atual} em estoque.', 'danger')
        return redirect(url_for('storeroom.dashboard'))


        
    # Calcula novo estoque
    produto.quantidade_atual = quantidade_atual + quantidade if tipo == 'ENTRADA' else quantidade_atual - quantidade
    
    # Atualiza Produto
    # Registra Movimentação
    nova_movimentacao = AlmoxMovimentacao(
        produto_id=produto_id, tipo=tipo, quantidade=quantidade,
        usuario=session.get('username', 'Sistema'), destino_id=destino_id,
        observacao=observacao
    )
    db.session.add(nova_movimentacao)
    
    db.session.commit()
    _queue_product_sync(produto)
    _queue_movement_sync(nova_movimentacao)
    flash(f'Tudo certo! A {tipo.capitalize()} de <b>{quantidade}x {produto.nome}</b> foi registrada com sucesso!', 'success')
    
    return redirect(url_for('storeroom.dashboard'))

@storeroom_bp.route('/produtos/imprimir_qr/<int:id>')
@login_required
@permission_required('perm_almoxarifado')
def imprimir_qr(id):
    """Gera uma etiqueta QR Code simples para o produto."""
    produto = db.session.get(AlmoxProduto, id) # MODERNIZADO
    if not produto:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('storeroom.listar_produtos'))
        
    sku = produto.sku
    nome = produto.nome
    
    # Gera a imagem do QR Code
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_Q, box_size=5, border=2)
    qr.add_data(sku)  # O leitor de código lerá o SKU exato
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    buffered = io.BytesIO()
    qr_img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode('utf-8')
    qr_base64 = f"data:image/png;base64,{img_str}"
    
    return render_template('storeroom/imprimir_qr.html', sku=sku, nome=nome, qr_base64=qr_base64)

@storeroom_bp.route('/relatorio_baixo_estoque')
@login_required
@permission_required('perm_almoxarifado')
def relatorio_baixo_estoque():
    """Gera um relatório em Excel dos itens em baixo estoque."""
    conn = db.engine
    query = "SELECT sku as 'SKU', nome as 'Produto', categoria as 'Categoria', quantidade_atual as 'Estoque Atual', estoque_minimo as 'Estoque Mínimo' FROM almox_produtos WHERE quantidade_atual <= estoque_minimo ORDER BY quantidade_atual ASC"
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        flash('Não há itens em baixo estoque para exportar.', 'info')
        return redirect(url_for('storeroom.dashboard'))
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Baixo_Estoque')
    
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f'relatorio_estoque_baixo_{datetime.now().strftime("%Y%m%d")}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@storeroom_bp.route('/exportar_estoque')
@login_required
@permission_required('perm_almoxarifado')
def exportar_estoque():
    """Gera um relatório em Excel de TODO o estoque do Almoxarifado."""
    conn = db.engine
    query = "SELECT sku as 'SKU', nome as 'Produto', categoria as 'Categoria', quantidade_atual as 'Estoque Atual', estoque_minimo as 'Estoque Mínimo', custo_unitario as 'Custo Unitário (R$)' FROM almox_produtos ORDER BY nome ASC"
    df = pd.read_sql_query(query, conn)
    
    if df.empty:
        flash('Não há itens no estoque para exportar.', 'info')
        return redirect(url_for('storeroom.listar_produtos'))
        
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Estoque_Completo')
    
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f'relatorio_estoque_completo_{datetime.now().strftime("%Y%m%d")}.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@storeroom_bp.route('/importar', methods=('GET', 'POST'))
@login_required
@permission_required('perm_almoxarifado')
def importar():
    """Importação em massa de produtos para o almoxarifado via Excel."""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('Nenhum arquivo enviado.', 'danger')
            return redirect(url_for('storeroom.importar'))
        
        file = request.files['file']
        if file.filename == '':
            flash('Nenhum arquivo selecionado.', 'danger')
            return redirect(url_for('storeroom.importar'))
            
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Por favor, envie um arquivo Excel (.xlsx ou .xls).', 'danger')
            return redirect(url_for('storeroom.importar'))
            
        try:
            df = pd.read_excel(file)
            df.columns = [str(c).strip().upper() for c in df.columns]
            
            required_cols = ['SKU', 'NOME']
            for col in required_cols:
                if col not in df.columns:
                    flash(f'ERRO: O Excel deve conter no mínimo as colunas {required_cols}. Baixe a planilha de exemplo.', 'danger')
                    return redirect(url_for('storeroom.importar'))
            
            # Remove linhas sem SKU ou Nome
            df = df.dropna(subset=['SKU', 'NOME'])
            
            if df.empty:
                flash('A planilha está vazia ou não contém SKUs/Nomes válidos.', 'danger')
                return redirect(url_for('storeroom.importar'))
            
            # Remove duplicados dentro da planilha
            df = df.drop_duplicates(subset=['SKU'])
            
            # Verifica existentes no banco
            skus_planilha = [str(x).strip().upper() for x in df['SKU'].tolist()]
            existentes_query = db.session.query(AlmoxProduto.sku).filter(AlmoxProduto.sku.in_(skus_planilha)).all()
            existentes = [row.sku for row in existentes_query]
            if existentes:
                flash(f'BLOQUEIO: Os seguintes SKUs já existem no sistema: {", ".join(existentes[:5])}... Remova-os da planilha para importar os novos.', 'danger')
                return redirect(url_for('storeroom.importar'))

            usuario = session.get('username', 'Sistema')
            cadastrados = 0
            produtos_importados = []
            movimentacoes_importadas = []
            
            for index, row in df.iterrows():
                sku = str(row['SKU']).strip().upper()
                nome = str(row['NOME']).strip().upper()
                categoria = str(row.get('CATEGORIA', 'OUTROS')).strip() if pd.notna(row.get('CATEGORIA')) else 'OUTROS'
                
                qtd_inicial = 0
                if 'QUANTIDADE_INICIAL' in df.columns and pd.notna(row['QUANTIDADE_INICIAL']):
                    try: qtd_inicial = int(row['QUANTIDADE_INICIAL'])
                    except: pass
                    
                est_minimo = 5
                if 'ESTOQUE_MINIMO' in df.columns and pd.notna(row['ESTOQUE_MINIMO']):
                    try: est_minimo = int(row['ESTOQUE_MINIMO'])
                    except: pass
                    
                custo = 0.0
                if 'CUSTO_UNITARIO' in df.columns and pd.notna(row['CUSTO_UNITARIO']):
                    try: custo = float(row['CUSTO_UNITARIO'])
                    except: pass

                novo_produto = AlmoxProduto(
                    sku=sku, nome=nome, categoria=categoria, quantidade_atual=qtd_inicial,
                    estoque_minimo=est_minimo, custo_unitario=custo
                )
                db.session.add(novo_produto)
                db.session.flush()
                produtos_importados.append(novo_produto)
                
                if qtd_inicial > 0:
                    nova_movimentacao = AlmoxMovimentacao(produto_id=novo_produto.id, tipo='ENTRADA', quantidade=qtd_inicial,
                                                        usuario=usuario, destino_id='Estoque Inicial Lote', observacao='Importação em Lote')
                    db.session.add(nova_movimentacao)
                    movimentacoes_importadas.append(nova_movimentacao)
                
                cadastrados += 1
            
            db.session.commit()
            for produto in produtos_importados:
                _queue_product_sync(produto)
            for movimentacao in movimentacoes_importadas:
                _queue_movement_sync(movimentacao)
            flash(f'Importação concluída com Sucesso! {cadastrados} produtos adicionados ao catálogo.', 'success')
            return redirect(url_for('storeroom.listar_produtos'))
            
        except Exception as e:
            flash(f'Erro ao processar o arquivo Excel: {str(e)}', 'danger')
            return redirect(url_for('storeroom.importar'))
            
    return render_template('storeroom/importar.html')

@storeroom_bp.route('/download_template_excel')
@login_required
@permission_required('perm_almoxarifado')
def download_template_excel():
    output = io.BytesIO()
    df = pd.DataFrame(columns=['SKU', 'NOME', 'CATEGORIA', 'QUANTIDADE_INICIAL', 'ESTOQUE_MINIMO'])
    df.loc[0] = ['CABO-HDMI-2M', 'CABO HDMI 2 METROS', 'Cabos', 50, 10]
    df.loc[1] = ['MSE-DELL-USB', 'MOUSE DELL USB', 'Periféricos', 30, 5]
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Template_Almoxarifado')
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='modelo_importacao_almoxarifado.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@storeroom_bp.route('/historico')
@login_required
@permission_required('perm_almoxarifado')
def historico():
    """Tela dedicada de histórico com filtros."""
    # Captura os filtros. Se for o primeiro acesso à tela (sem parâmetros), adota a data atual como padrão.
    if not request.args:
        data_inicio = datetime.now().strftime('%Y-%m-%d')
        data_fim = datetime.now().strftime('%Y-%m-%d')
    else:
        data_inicio = request.args.get('data_inicio', '')
        data_fim = request.args.get('data_fim', '')

    tipo = request.args.get('tipo', '')
    busca = request.args.get('busca', '').strip()
    
    query = db.session.query(AlmoxMovimentacao, AlmoxProduto.nome, AlmoxProduto.sku).join(
        AlmoxProduto, AlmoxMovimentacao.produto_id == AlmoxProduto.id # Esta linha está correta
    )
    
    # CORREÇÃO: Converte as strings de data para objetos datetime para comparação
    if data_inicio:
        try:
            dt_inicio_obj = datetime.strptime(f"{data_inicio} 00:00:00", '%Y-%m-%d %H:%M:%S')
            query = query.filter(AlmoxMovimentacao.data_movimentacao >= dt_inicio_obj)
        except ValueError:
            pass # Ignora data inválida
    if data_fim:
        try:
            dt_fim_obj = datetime.strptime(f"{data_fim} 23:59:59", '%Y-%m-%d %H:%M:%S')
            query = query.filter(AlmoxMovimentacao.data_movimentacao <= dt_fim_obj)
        except ValueError:
            pass # Ignora data inválida


    if tipo:
        query = query.filter(AlmoxMovimentacao.tipo == tipo)
        
    if busca:
        busca_like = f"%{busca}%"
        query = query.filter(db.or_(AlmoxProduto.nome.like(busca_like), AlmoxProduto.sku.like(busca_like), AlmoxMovimentacao.usuario.like(busca_like), AlmoxMovimentacao.destino_id.like(busca_like)))
        
    movimentacoes = query.order_by(AlmoxMovimentacao.id.desc()).limit(500).all()

    # Processa as movimentações para formatar a data de forma segura
    movimentacoes_processadas = [] # CORREÇÃO: Garante que esta lista seja sempre definida
    for mov, nome, sku in movimentacoes: # mov é um objeto AlmoxMovimentacao, nome e sku são strings
        mov_dict = {
            'id': mov.id,
            'produto_id': mov.produto_id,
            'tipo': mov.tipo,
            'quantidade': mov.quantidade,
            'usuario': mov.usuario,
            'destino_id': mov.destino_id,
            'observacao': mov.observacao,
            'nome_produto': nome,
            'sku_produto': sku,
            'data_formatada': mov.data_movimentacao.strftime('%d/%m/%Y %H:%M') if isinstance(mov.data_movimentacao, datetime) else ''
        }
        movimentacoes_processadas.append(mov_dict) # CORREÇÃO: Adiciona o dicionário processado

    # CORREÇÃO: Categorias para o filtro
    categorias_query = db.session.query(AlmoxProduto.categoria).filter(AlmoxProduto.categoria != None, AlmoxProduto.categoria != '').distinct().order_by(AlmoxProduto.categoria)
    categorias = [row.categoria for row in categorias_query]

    return render_template('storeroom/historico.html', 
                           movimentacoes=movimentacoes_processadas,
                           data_inicio=data_inicio, 
                           data_fim=data_fim, 
                           filtro_tipo=tipo, 
                           filtro_busca=busca,
                           categorias=categorias) # CORREÇÃO: Passa categorias para o template

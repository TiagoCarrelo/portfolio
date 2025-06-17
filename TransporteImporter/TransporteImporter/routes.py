import re
from datetime import datetime, timedelta
from flask import render_template, request, redirect, url_for, flash
from app import app, db
from models import Cliente, Agendamento

@app.route('/')
def index():
    """Página inicial - redireciona para importar"""
    return redirect(url_for('importar'))

@app.route('/importar', methods=['GET', 'POST'])
def importar():
    """Página para importar clientes"""
    if request.method == 'POST':
        mensagem = request.form.get('mensagem', '').strip()
        
        if not mensagem:
            flash('Por favor, insira a mensagem com os dados dos clientes.', 'error')
            return render_template('importar.html')
        
        # Processar mensagem e mostrar pré-visualização
        return redirect(url_for('preview_clientes', mensagem=mensagem))
    
    return render_template('importar.html')

@app.route('/preview')
def preview_clientes():
    """Pré-visualização dos clientes extraídos da mensagem"""
    mensagem = request.args.get('mensagem', '')
    
    if not mensagem:
        flash('Mensagem não encontrada.', 'error')
        return redirect(url_for('importar'))
    
    try:
        # Processar mensagem sem salvar na base de dados
        clientes_processados = processar_mensagem_preview(mensagem)
        
        if not clientes_processados:
            flash('Nenhum cliente foi encontrado na mensagem. Verifique o formato dos dados.', 'warning')
            return redirect(url_for('importar'))
        
        # Agrupar clientes por região
        clientes_por_regiao = {}
        for cliente in clientes_processados:
            regiao = cliente['regiao']
            if regiao not in clientes_por_regiao:
                clientes_por_regiao[regiao] = []
            clientes_por_regiao[regiao].append(cliente)
        
        return render_template('preview.html', 
                             clientes_por_regiao=clientes_por_regiao,
                             mensagem_original=mensagem)
    
    except Exception as e:
        app.logger.error(f'Erro ao processar mensagem: {str(e)}')
        flash(f'Erro ao processar mensagem: {str(e)}', 'error')
        return redirect(url_for('importar'))

@app.route('/confirmar_importacao', methods=['POST'])
def confirmar_importacao():
    """Confirma e salva os clientes na base de dados"""
    mensagem = request.form.get('mensagem_original', '')
    
    if not mensagem:
        flash('Mensagem não encontrada.', 'error')
        return redirect(url_for('importar'))
    
    try:
        # Processar e salvar na base de dados
        resultado = processar_mensagem_seguro(mensagem)
        
        if resultado['clientes_importados']:
            total_clientes = len(resultado['clientes_importados'])
            regioes_detectadas = ', '.join(resultado['regioes_detectadas'])
            flash(f'Importados {total_clientes} clientes com sucesso! Regiões: {regioes_detectadas}', 'success')
            return redirect(url_for('agenda'))
        else:
            flash('Erro ao importar clientes.', 'error')
            return redirect(url_for('importar'))
    
    except Exception as e:
        app.logger.error(f'Erro ao confirmar importação: {str(e)}')
        flash(f'Erro ao confirmar importação: {str(e)}', 'error')
        return redirect(url_for('importar'))

def processar_mensagem_preview(mensagem):
    """
    Processa mensagem do seguro apenas para pré-visualização (sem salvar na BD)
    """
    clientes_processados = []
    
    # Dividir por vírgulas ou hífens para separar cada cliente
    separadores = [',', ' - ', '-']
    clientes_texto = [mensagem]
    
    # Aplicar separadores sequencialmente
    for sep in separadores:
        novos_clientes = []
        for cliente_txt in clientes_texto:
            novos_clientes.extend(cliente_txt.split(sep))
        clientes_texto = novos_clientes
    
    for cliente_txt in clientes_texto:
        cliente_txt = cliente_txt.strip()
        if not cliente_txt:
            continue
            
        try:
            # Extrair dados do cliente usando padrões
            dados_cliente = extrair_dados_cliente_seguro(cliente_txt)
            
            if dados_cliente:
                # Detectar região geograficamente
                regiao = detectar_regiao_geografica(dados_cliente['morada'], dados_cliente['destino'])
                dados_cliente['regiao'] = regiao
                dados_cliente['dados_originais'] = cliente_txt
                
                clientes_processados.append(dados_cliente)
        
        except Exception as e:
            app.logger.warning(f'Erro ao processar cliente "{cliente_txt}": {str(e)}')
            continue
    
    return clientes_processados

@app.route('/gerar_mensagem_whatsapp/<regiao>')
def gerar_mensagem_whatsapp(regiao):
    """Gera mensagem de WhatsApp com todos os clientes de uma região"""
    try:
        clientes = Cliente.query.filter_by(regiao=regiao).all()
        
        if not clientes:
            flash(f'Nenhum cliente encontrado na região {regiao}.', 'info')
            return redirect(url_for('agenda'))
        
        # Gerar mensagem formatada
        mensagem_lines = []
        mensagem_lines.append(f"📋 *Lista de Clientes - Motorista {regiao}*")
        mensagem_lines.append(f"📅 Data: {datetime.now().strftime('%d/%m/%Y')}")
        mensagem_lines.append("")
        
        for i, cliente in enumerate(clientes, 1):
            mensagem_lines.append(f"*{i}. {cliente.nome}*")
            mensagem_lines.append(f"🏠 Morada: {cliente.morada}")
            mensagem_lines.append(f"🏥 Destino: {cliente.destino}")
            mensagem_lines.append(f"⏰ Horário: {cliente.horario}")
            mensagem_lines.append(f"📞 Contacto: {cliente.contacto}")
            mensagem_lines.append("")
        
        mensagem_lines.append(f"Total: {len(clientes)} clientes")
        
        mensagem_whatsapp = "\n".join(mensagem_lines)
        
        return render_template('mensagem_whatsapp.html', 
                             mensagem=mensagem_whatsapp,
                             regiao=regiao,
                             total_clientes=len(clientes))
    
    except Exception as e:
        app.logger.error(f'Erro ao gerar mensagem WhatsApp para região {regiao}: {str(e)}')
        flash(f'Erro ao gerar mensagem para a região {regiao}.', 'error')
        return redirect(url_for('agenda'))

@app.route('/agendamento/<int:agendamento_id>/finalizar', methods=['POST'])
def finalizar_agendamento(agendamento_id):
    """Marca um agendamento como finalizado e atualiza status do cliente"""
    try:
        agendamento = Agendamento.query.get_or_404(agendamento_id)
        agendamento.status = 'Concluído'
        
        # Marcar cliente como transportado
        agendamento.cliente.status_cliente = 'Transportado'
        
        db.session.commit()
        
        flash(f'Agendamento de {agendamento.cliente.nome} finalizado com sucesso!', 'success')
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Erro ao finalizar agendamento {agendamento_id}: {str(e)}')
        flash('Erro ao finalizar agendamento.', 'error')
    
    return redirect(url_for('agenda'))

@app.route('/agendamento/<int:agendamento_id>/apagar', methods=['POST'])
def apagar_agendamento(agendamento_id):
    """Remove um agendamento da base de dados e marca cliente como removido"""
    try:
        agendamento = Agendamento.query.get_or_404(agendamento_id)
        cliente_nome = agendamento.cliente.nome
        
        # Marcar cliente como removido em vez de apagar o agendamento
        agendamento.cliente.status_cliente = 'Removido'
        agendamento.status = 'Cancelado'
        
        db.session.commit()
        
        flash(f'Agendamento de {cliente_nome} cancelado e cliente marcado como removido!', 'success')
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Erro ao apagar agendamento {agendamento_id}: {str(e)}')
        flash('Erro ao remover agendamento.', 'error')
    
    return redirect(url_for('agenda'))

@app.route('/limpar_lista_clientes', methods=['POST'])
def limpar_lista_clientes():
    """Remove apenas os clientes da lista (mantém agendamentos históricos)"""
    try:
        # Contar clientes antes de apagar
        num_clientes = Cliente.query.count()
        
        # Apagar agendamentos primeiro (devido à chave estrangeira)
        Agendamento.query.delete()
        
        # Apagar clientes
        Cliente.query.delete()
        
        db.session.commit()
        
        flash(f'Lista de clientes limpa com sucesso! Removidos {num_clientes} clientes.', 'success')
    
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Erro ao limpar lista de clientes: {str(e)}')
        flash('Erro ao limpar lista de clientes.', 'error')
    
    return redirect(url_for('agenda'))

@app.route('/agenda')
def agenda():
    """Página para visualizar a agenda de clientes"""
    # Verificar filtro de status
    mostrar_concluidos = request.args.get('mostrar_concluidos', 'false').lower() == 'true'
    
    # Buscar todos os clientes ordenados por data de criação
    clientes = Cliente.query.order_by(Cliente.data_criacao.desc()).all()
    
    # Buscar agendamentos baseado no filtro
    if mostrar_concluidos:
        agendamentos = Agendamento.query.join(Cliente).order_by(Agendamento.data_agendamento.asc()).all()
    else:
        agendamentos = Agendamento.query.join(Cliente).filter(Agendamento.status == 'Agendado').order_by(Agendamento.data_agendamento.asc()).all()
    
    return render_template('agenda.html', 
                         clientes=clientes,
                         agendamentos=agendamentos,
                         mostrar_concluidos=mostrar_concluidos)

@app.route('/cliente/<int:cliente_id>/agendar', methods=['POST'])
def agendar_cliente(cliente_id):
    """Criar agendamento para um cliente"""
    cliente = Cliente.query.get_or_404(cliente_id)
    
    data_str = request.form.get('data_agendamento')
    observacoes = request.form.get('observacoes', '')
    
    if not data_str:
        flash('Por favor, selecione uma data para o agendamento.', 'error')
        return redirect(url_for('agenda'))
    
    try:
        data_agendamento = datetime.strptime(data_str, '%Y-%m-%dT%H:%M')
        
        # Criar novo agendamento
        agendamento = Agendamento(
            cliente_id=cliente.id,
            data_agendamento=data_agendamento,
            observacoes=observacoes
        )
        
        db.session.add(agendamento)
        db.session.commit()
        
        flash(f'Agendamento criado para {cliente.nome}!', 'success')
    
    except ValueError:
        flash('Formato de data inválido.', 'error')
    except Exception as e:
        app.logger.error(f'Erro ao criar agendamento: {str(e)}')
        flash('Erro ao criar agendamento.', 'error')
    
    return redirect(url_for('agenda'))

def processar_mensagem_seguro(mensagem):
    """
    Processa mensagem do seguro onde cada cliente termina com vírgula ou hífen
    Formato: Nome Horário Destino Morada Contacto, Nome Horário Destino Morada Contacto
    """
    clientes_importados = []
    regioes_detectadas = set()
    
    # Dividir por vírgulas ou hífens para separar cada cliente
    separadores = [',', ' - ', '-']
    clientes_texto = [mensagem]
    
    # Aplicar separadores sequencialmente
    for sep in separadores:
        novos_clientes = []
        for cliente_txt in clientes_texto:
            novos_clientes.extend(cliente_txt.split(sep))
        clientes_texto = novos_clientes
    
    for cliente_txt in clientes_texto:
        cliente_txt = cliente_txt.strip()
        if not cliente_txt:
            continue
            
        try:
            # Extrair dados do cliente usando padrões
            dados_cliente = extrair_dados_cliente_seguro(cliente_txt)
            
            if dados_cliente:
                # Detectar região geograficamente baseado no destino e morada
                regiao = detectar_regiao_geografica(dados_cliente['morada'], dados_cliente['destino'])
                dados_cliente['regiao'] = regiao
                regioes_detectadas.add(regiao)
                
                # Log da detecção para controle
                app.logger.info(f'Cliente {dados_cliente["nome"]}: Destino="{dados_cliente["destino"]}", Morada="{dados_cliente["morada"]}" -> Motorista da região {regiao}')
                
                # Verificar se cliente já existe
                cliente_existente = Cliente.query.filter_by(
                    nome=dados_cliente['nome'],
                    contacto=dados_cliente['contacto']
                ).first()
                
                if not cliente_existente:
                    dados_cliente['dados_originais'] = cliente_txt
                    
                    cliente = Cliente(**dados_cliente)
                    db.session.add(cliente)
                    db.session.flush()  # Garantir que o cliente tenha ID antes de criar agendamento
                    
                    # Criar agendamento automático
                    data_agendamento = calcular_data_agendamento(
                        dados_cliente['horario'], 
                        len(clientes_importados)
                    )
                    agendamento = Agendamento(
                        cliente_id=cliente.id,
                        data_agendamento=data_agendamento,
                        observacoes=f'Agendamento automático - Destino: {dados_cliente["destino"]}'
                    )
                    db.session.add(agendamento)
                    
                    clientes_importados.append(cliente)
        
        except Exception as e:
            app.logger.warning(f'Erro ao processar cliente "{cliente_txt}": {str(e)}')
            db.session.rollback()  # Fazer rollback em caso de erro
            continue
    
    try:
        if clientes_importados:
            db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Erro ao fazer commit dos clientes: {str(e)}')
        raise
    
    return {
        'clientes_importados': clientes_importados,
        'regioes_detectadas': list(regioes_detectadas)
    }

def extrair_dados_cliente_seguro(texto):
    """
    Extrai dados do cliente de um texto no formato:
    Nome Horário Destino NomeSeguro Morada Contacto
    Exemplo: João Silva 14:00 Hospital São José seguro fidelidade Rua das Flores 12 912345678
    """
    texto = texto.strip()
    if not texto:
        return None
    
    # Padrão para extrair contacto (números no final)
    padrao_contacto = r'(\d{9,15})$'
    match_contacto = re.search(padrao_contacto, texto)
    
    if not match_contacto:
        return None
    
    contacto = match_contacto.group(1)
    resto_texto = texto[:match_contacto.start()].strip()
    
    # Padrão para extrair horário (formato HH:MM ou HHhMM)
    padrao_horario = r'(\d{1,2}[:h]\d{0,2}|\d{1,2}h|\d{1,2}:\d{2})'
    match_horario = re.search(padrao_horario, resto_texto)
    
    if not match_horario:
        return None
    
    horario = match_horario.group(1)
    
    # Dividir o resto em nome (antes do horário) e resto (depois)
    pos_horario = match_horario.start()
    nome = resto_texto[:pos_horario].strip()
    resto_depois_horario = resto_texto[match_horario.end():].strip()
    
    if not nome or not resto_depois_horario:
        return None
    
    # Procurar pela palavra "seguro" para identificar o nome do seguro
    palavras = resto_depois_horario.split()
    pos_seguro = None
    
    for i, palavra in enumerate(palavras):
        if palavra.lower() == 'seguro':
            pos_seguro = i
            break
    
    if pos_seguro is None:
        # Se não encontrar "seguro", assumir formato antigo: destino + morada
        return extrair_formato_antigo(nome, horario, resto_depois_horario, contacto)
    
    # Separar destino (antes de "seguro"), nome do seguro e morada (depois)
    destino_palavras = palavras[:pos_seguro]
    destino = ' '.join(destino_palavras)
    
    # Encontrar onde termina o nome do seguro e começa a morada
    palavras_depois_seguro = palavras[pos_seguro:]
    palavras_endereco = ['rua', 'avenida', 'av', 'travessa', 'largo', 'praça', 'estrada']
    
    pos_endereco = None
    for i, palavra in enumerate(palavras_depois_seguro):
        if palavra.lower() in palavras_endereco:
            pos_endereco = i
            break
    
    if pos_endereco:
        nome_seguro = ' '.join(palavras_depois_seguro[:pos_endereco])
        morada = ' '.join(palavras_depois_seguro[pos_endereco:])
    else:
        # Se não encontrar palavra de endereço, dividir no meio das palavras restantes
        meio = len(palavras_depois_seguro) // 2
        if meio < 2:
            meio = 2
        nome_seguro = ' '.join(palavras_depois_seguro[:meio])
        morada = ' '.join(palavras_depois_seguro[meio:])
    
    return {
        'nome': nome,
        'horario': horario,
        'destino': destino,
        'nome_seguro': nome_seguro,
        'morada': morada,
        'contacto': contacto
    }

def extrair_formato_antigo(nome, horario, resto_texto, contacto):
    """
    Fallback para formato antigo sem nome do seguro
    """
    palavras = resto_texto.split()
    palavras_endereco = ['rua', 'avenida', 'av', 'travessa', 'largo', 'praça', 'estrada']
    
    pos_endereco = None
    for i, palavra in enumerate(palavras):
        if palavra.lower() in palavras_endereco:
            pos_endereco = i
            break
    
    if pos_endereco:
        destino = ' '.join(palavras[:pos_endereco])
        morada = ' '.join(palavras[pos_endereco:])
    else:
        meio = len(palavras) // 2
        if meio < 2:
            meio = 2
        destino = ' '.join(palavras[:meio])
        morada = ' '.join(palavras[meio:])
    
    return {
        'nome': nome,
        'horario': horario,
        'destino': destino,
        'nome_seguro': '',
        'morada': morada,
        'contacto': contacto
    }

def detectar_regiao_geografica(morada, destino):
    """
    Detecta geograficamente onde fica o destino para entregar ao motorista da região correta
    Se não reconhecer a morada/destino, entrega para 'Geral' (chefe)
    """
    # Combinar destino e morada para análise geográfica completa
    texto_completo = f"{destino} {morada}".lower().strip()
    
    if not texto_completo:
        return 'Geral'
    
    # Base de dados geográfica expandida por região de motoristas
    regioes_geograficas = {
        'Lisboa': {
            'bairros': [
                'lisboa', 'benfica', 'alvalade', 'campo grande', 'marquês de pombal', 'rossio', 
                'chiado', 'bairro alto', 'príncipe real', 'avenidas novas', 'saldanha', 'picoas',
                'areeiro', 'arroios', 'avenida da república', 'entrecampos', 'campolide',
                'telheiras', 'olivais', 'parque das nações', 'oriente', 'chelas', 'marvila',
                'beato', 'penha de frança', 'graça', 'mouraria', 'anjos', 'estrela', 'lapa',
                'campo de ourique', 'amoreiras', 'rato', 'santa apolónia', 'cais do sodré',
                'santos', 'alcântara', 'ajuda'
            ],
            'hospitais': [
                'hospital santa maria', 'hospital dona estefânia', 'hospital são josé',
                'hospital curry cabral', 'hospital pulido valente', 'hospital egas moniz',
                'centro hospitalar lisboa norte', 'centro hospitalar lisboa central',
                'hospital cruz vermelha', 'hospital luz lisboa', 'hospital cuf descobertas',
                'clínica central', 'clínica de lisboa', 'centro clínico', 'policlínica',
                'hospital de santa maria', 'hospital curry cabral', 'instituto português oncologia'
            ],
            'transportes': [
                'aeroporto lisboa', 'aeroporto portela', 'gare do oriente', 'estação santa apolónia',
                'estação rossio', 'estação cais do sodré', 'metro lisboa'
            ],
            'codigos': ['1000', '1050', '1100', '1150', '1200', '1250', '1300', '1350', '1400', '1450', '1500', '1600', '1700']
        },
        
        'Sintra': {
            'localidades': [
                'sintra', 'cascais', 'estoril', 'oeiras', 'queluz', 'mem martins', 
                'agualva-cacém', 'rio de mouro', 'massamá', 'algueirão', 'belas',
                'monte abraão', 'barcarena', 'linda-a-velha', 'algés', 'carnaxide',
                'paço de arcos', 'carcavelos', 'são joão do estoril', 'monte estoril',
                'alcabideche', 'malveira', 'venda do pinheiro', 'mira sintra'
            ],
            'hospitais': [
                'hospital fernando fonseca', 'hospital amadora-sintra', 'clínica sintra',
                'clínica cascais', 'hospital cuf cascais'
            ],
            'pontos_interesse': [
                'quinta da regaleira', 'palácio da pena', 'casino estoril',
                'centro colombo', 'aqueduto águas livres', 'cintramedica',
                'cintramedica portela', 'portela sintra'
            ],
            'codigos': ['2710', '2715', '2720', '2730', '2735', '2740', '2750', '2760', '2770', '2775', '2780', '2785', '2790']
        },
        
        'Piquete': {
            'localidades': [
                'loures', 'odivelas', 'amadora', 'brandoa', 'reboleira', 'pontinha',
                'alfragide', 'venteira', 'lumiar', 'carnide', 'damaia', 'buraca',
                'falagueira', 'venda nova', 'famões', 'frielas', 'moscavide',
                'sacavém', 'prior velho', 'bobadela', 'santo antão do tojal',
                'santa iria de azóia', 'alverca', 'vila franca de xira'
            ],
            'pontos_interesse': [
                'centro comercial colombo', 'hospital beatriz ângelo', 'aeroporto lisboa proximidade',
                'quinta das conchas', 'pavilhão atlântico'
            ],
            'codigos': ['2650', '2660', '2670', '2680', '2690', '2700']
        },
        
        'Porto': {
            'localidades': [
                'porto', 'matosinhos', 'vila nova de gaia', 'gondomar', 'valongo',
                'maia', 'póvoa de varzim', 'vila do conde', 'santo tirso', 'trofa',
                'paços de ferreira', 'paredes', 'penafiel', 'lousada', 'felgueiras',
                'marco de canaveses', 'amarante', 'ermesinde', 'rio tinto'
            ],
            'pontos_interesse': [
                'aeroporto francisco sá carneiro', 'hospital são joão', 'hospital santo antónio',
                'estação são bento', 'estação campanhã', 'centro comercial dolce vita'
            ],
            'codigos': ['4000', '4050', '4100', '4150', '4200', '4250', '4300', '4350', '4400', '4450', '4460', '4470']
        },
        
        'Setúbal': {
            'localidades': [
                'setúbal', 'almada', 'barreiro', 'moita', 'montijo', 'alcochete',
                'palmela', 'sesimbra', 'seixal', 'corroios', 'fernão ferro',
                'charneca de caparica', 'costa da caparica', 'trafaria', 'cacilhas',
                'pragal', 'cova da piedade', 'laranjeiro', 'feijó'
            ],
            'pontos_interesse': [
                'hospital garcia de horta', 'hospital do barreiro', 'ponte 25 de abril',
                'ponte vasco da gama', 'estação roma-areeiro', 'forum montijo'
            ],
            'codigos': ['2800', '2810', '2820', '2830', '2840', '2845', '2850', '2860', '2870', '2890']
        },
        
        'Coimbra': {
            'localidades': [
                'coimbra', 'figueira da foz', 'aveiro', 'viseu', 'leiria',
                'pombal', 'marinha grande', 'óbidos', 'caldas da rainha',
                'torres vedras', 'peniche', 'nazaré', 'alcobaça', 'batalha',
                'porto de mós', 'rio maior', 'santarém', 'cartaxo', 'torres novas'
            ],
            'pontos_interesse': [
                'universidade de coimbra', 'hospital universitário coimbra',
                'centro hospitalar baixo vouga', 'hospital de leiria'
            ],
            'codigos': ['3000', '3020', '3030', '3040', '3050', '3060', '3070', '3080', '3090']
        }
    }
    
    # Primeira prioridade: procurar correspondências exatas nos destinos e pontos de interesse
    for regiao, dados in regioes_geograficas.items():
        # Verificar pontos de interesse específicos (hospitais, aeroportos, etc.)
        if 'pontos_interesse' in dados:
            for ponto in dados['pontos_interesse']:
                if ponto in texto_completo:
                    return regiao
        
        # Verificar hospitais específicos
        if 'hospitais' in dados:
            for hospital in dados['hospitais']:
                if hospital in texto_completo:
                    return regiao
        
        # Verificar transportes específicos
        if 'transportes' in dados:
            for transporte in dados['transportes']:
                if transporte in texto_completo:
                    return regiao
    
    # Segunda prioridade: verificar bairros e localidades
    for regiao, dados in regioes_geograficas.items():
        campos_localidade = ['bairros', 'localidades']
        for campo in campos_localidade:
            if campo in dados:
                for localidade in dados[campo]:
                    if localidade in texto_completo:
                        return regiao
    
    # Terceira prioridade: códigos postais
    for regiao, dados in regioes_geograficas.items():
        if 'codigos' in dados:
            for codigo in dados['codigos']:
                if codigo in texto_completo:
                    return regiao
    
    # Quarta prioridade: análise de palavras-chave de proximidade
    proximidades = {
        'Lisboa': ['centro', 'baixa', 'metro azul', 'metro amarela', 'metro verde', 'metro vermelha', 'rua das flores'],
        'Sintra': ['linha sintra', 'costa', 'praia', 'marginal'],
        'Setúbal': ['sul', 'ponte', 'margem sul', 'ferry', 'cacilheiro'],
        'Porto': ['norte', 'douro', 'metro porto'],
        'Coimbra': ['centro portugal', 'região centro']
    }
    
    for regiao, palavras in proximidades.items():
        for palavra in palavras:
            if palavra in texto_completo:
                return regiao
    
    # Quinta prioridade: análise de contexto por palavras genéricas de saúde em Lisboa por defeito
    palavras_saude_lisboa = ['clínica', 'centro médico', 'consultório', 'centro de saúde']
    for palavra in palavras_saude_lisboa:
        if palavra in texto_completo and 'central' in texto_completo:
            return 'Lisboa'  # Assumir clínicas centrais como Lisboa
    
    # Se não conseguir identificar geograficamente, entregar ao Geral (chefe)
    return 'Geral'

def calcular_data_agendamento(horario_preferencial, indice_cliente):
    """
    Calcula a data de agendamento baseado no horário preferencial do cliente
    """
    try:
        # Tentar extrair hora do horário preferencial
        hora_match = re.search(r'(\d{1,2}):?(\d{0,2})', horario_preferencial)
        
        if hora_match:
            hora = int(hora_match.group(1))
            minuto = int(hora_match.group(2)) if hora_match.group(2) else 0
            
            # Validar horário
            if 0 <= hora <= 23 and 0 <= minuto <= 59:
                # Agendar para o próximo dia útil
                data_base = datetime.now() + timedelta(days=indice_cliente + 1)
                
                # Se for fim de semana, mover para segunda-feira
                while data_base.weekday() >= 5:  # 5=sábado, 6=domingo
                    data_base += timedelta(days=1)
                
                return data_base.replace(hour=hora, minute=minuto, second=0, microsecond=0)
    
    except (ValueError, AttributeError):
        pass
    
    # Horário padrão se não conseguir extrair horário específico
    data_base = datetime.now() + timedelta(days=indice_cliente + 1)
    while data_base.weekday() >= 5:
        data_base += timedelta(days=1)
    
    return data_base.replace(hour=9, minute=0, second=0, microsecond=0)

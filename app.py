"""
E-Shop Brasil - Central de Dados
Aplicação Streamlit + MongoDB para inserir, editar, concatenar e analisar
dados de clientes, produtos e pedidos de um e-commerce de grande porte.
"""

import hashlib
import json
import os
import random
import re
import time
from datetime import datetime, timedelta
from datetime import time as dtime
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from bson import ObjectId, json_util
from bson.errors import InvalidId
from faker import Faker
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.errors import BulkWriteError, PyMongoError

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB", "eshop_brasil")
LGPD_SALT = os.getenv("LGPD_SALT", "eshop-brasil-demo")
PASTA_DADOS = Path(__file__).parent / "dados"

st.set_page_config(page_title="E-Shop Brasil | Central de Dados", page_icon="🛒", layout="wide")

# Cidades atendidas (cidade, UF, peso aproximado de população)
CIDADES = [
    ("São Paulo", "SP", 12), ("Campinas", "SP", 3), ("Rio de Janeiro", "RJ", 7), ("Niterói", "RJ", 1),
    ("Belo Horizonte", "MG", 4), ("Uberlândia", "MG", 1), ("Vitória", "ES", 1),
    ("Curitiba", "PR", 3), ("Londrina", "PR", 1), ("Porto Alegre", "RS", 3), ("Caxias do Sul", "RS", 1),
    ("Florianópolis", "SC", 2), ("Joinville", "SC", 1),
    ("Brasília", "DF", 3), ("Goiânia", "GO", 2), ("Campo Grande", "MS", 1), ("Cuiabá", "MT", 1),
    ("Salvador", "BA", 3), ("Recife", "PE", 3), ("Fortaleza", "CE", 3), ("São Luís", "MA", 1),
    ("Natal", "RN", 1), ("João Pessoa", "PB", 1), ("Maceió", "AL", 1), ("Teresina", "PI", 1), ("Aracaju", "SE", 1),
    ("Manaus", "AM", 2), ("Belém", "PA", 2), ("Porto Velho", "RO", 1), ("Macapá", "AP", 1),
    ("Rio Branco", "AC", 1), ("Boa Vista", "RR", 1), ("Palmas", "TO", 1),
]

UF_REGIAO = {
    **dict.fromkeys(["SP", "RJ", "MG", "ES"], "Sudeste"),
    **dict.fromkeys(["PR", "RS", "SC"], "Sul"),
    **dict.fromkeys(["DF", "GO", "MS", "MT"], "Centro-Oeste"),
    **dict.fromkeys(["BA", "PE", "CE", "MA", "RN", "PB", "AL", "PI", "SE"], "Nordeste"),
    **dict.fromkeys(["AM", "PA", "RO", "AP", "AC", "RR", "TO"], "Norte"),
}
REGIOES = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]

# Um centro de distribuição (CD) por região; Cajamar é o CD central
CD_POR_REGIAO = {
    "Sudeste": "CD Cajamar-SP", "Sul": "CD Curitiba-PR", "Centro-Oeste": "CD Goiânia-GO",
    "Nordeste": "CD Recife-PE", "Norte": "CD Manaus-AM",
}
CD_CENTRAL = "CD Cajamar-SP"
CDS = list(CD_POR_REGIAO.values())

PRAZO_BASE = {"Sudeste": 2, "Sul": 3, "Centro-Oeste": 4, "Nordeste": 4, "Norte": 6}
PRAZO_EXTRA_CENTRAL = {"Sudeste": 0, "Sul": 2, "Centro-Oeste": 3, "Nordeste": 5, "Norte": 8}
CHANCE_ATRASO = {"Sudeste": 0.08, "Sul": 0.10, "Centro-Oeste": 0.15, "Nordeste": 0.20, "Norte": 0.30}
FRETE_BASE = {"Sudeste": 12.9, "Sul": 16.9, "Centro-Oeste": 19.9, "Nordeste": 22.9, "Norte": 34.9}

CANAIS = ["Site", "App", "Loja física"]
MODALIDADES = ["Entrega em casa", "Retirada em loja", "Ponto de coleta"]
STATUS = ["Processando", "Em trânsito", "Entregue", "Cancelado"]

CATALOGO = {
    "Eletrônicos": (["Smartphone", "Fone Bluetooth", "Notebook", "Smart TV 50''", "Tablet", "Caixa de Som",
                     "Smartwatch", "Mouse Gamer", "Teclado Mecânico", "Carregador Turbo"],
                    ["Samsung", "Motorola", "Xiaomi", "LG", "JBL", "Lenovo", "Positivo", "Multilaser"], (49, 4500)),
    "Moda": (["Camiseta", "Calça Jeans", "Tênis Casual", "Jaqueta", "Vestido", "Bermuda", "Moletom", "Boné"],
             ["Hering", "Renner", "Nike", "Adidas", "Reserva", "Colcci"], (39, 499)),
    "Casa": (["Jogo de Panelas", "Cafeteira", "Liquidificador", "Jogo de Cama", "Air Fryer", "Aspirador",
              "Luminária", "Toalha de Banho"], ["Tramontina", "Electrolux", "Mondial", "Philco", "Arno", "Santista"], (29, 899)),
    "Esporte": (["Bola de Futebol", "Halter 5kg", "Bicicleta", "Tapete de Yoga", "Garrafa Térmica", "Corda de Pular"],
                ["Penalty", "Caloi", "Kikos", "Nike", "Stanley"], (19, 2200)),
    "Beleza": (["Perfume", "Shampoo", "Protetor Solar", "Base Líquida", "Secador de Cabelo", "Hidratante"],
               ["Natura", "O Boticário", "Eudora", "L'Oréal", "Taiff", "Nivea"], (15, 450)),
    "Livros": (["Romance", "Livro de Receitas", "Box de Fantasia", "Guia de Programação", "HQ", "Biografia"],
               ["Companhia das Letras", "Rocco", "Intrínseca", "Novatec", "Panini"], (19, 189)),
    "Brinquedos": (["Quebra-cabeça", "Boneca", "Carrinho de Controle", "Blocos de Montar", "Jogo de Tabuleiro"],
                   ["Estrela", "Mattel", "Hasbro", "Lego", "Grow"], (29, 699)),
}
CATEGORIAS = list(CATALOGO)
VARIANTES = ["Pro", "Max", "Lite", "Plus", "Basic", "Premium", "Slim", "Edição 2026", "Preto", "Azul", "Branco", "Vermelho"]


# ---------------------------------------------------------------------------
# Conexão e índices
# ---------------------------------------------------------------------------

@st.cache_resource
def conectar():
    cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
    db = cliente[DB_NAME]
    cliente.admin.command("ping")
    criar_indices(db)
    return db


def criar_indices(db):
    """Índices que sustentam as consultas mais frequentes da aplicação."""
    db.clientes.create_index("cpf_hash", unique=True)
    db.clientes.create_index("nome")
    db.clientes.create_index("estado")
    db.produtos.create_index("categoria")
    db.produtos.create_index("nome")
    db.pedidos.create_index([("data", DESCENDING)])
    db.pedidos.create_index("cliente_id")
    db.pedidos.create_index([("entrega.regiao", ASCENDING), ("data", DESCENDING)])
    db.pedidos.create_index("itens.produto_id")
    db.pedidos.create_index("status")


# ---------------------------------------------------------------------------
# LGPD: pseudonimização e mascaramento
# ---------------------------------------------------------------------------

def so_digitos(texto):
    return re.sub(r"\D", "", str(texto))


def hash_cpf(cpf):
    """O CPF nunca é gravado em claro: guardamos um hash SHA-256 com salt (pseudonimização)."""
    return hashlib.sha256((LGPD_SALT + so_digitos(cpf)).encode()).hexdigest()


def mascarar_cpf(cpf):
    d = so_digitos(cpf).zfill(11)
    return f"***.{d[3:6]}.{d[6:9]}-**"


def mascarar_email(email):
    if not email or "@" not in str(email):
        return email
    usuario, dominio = str(email).split("@", 1)
    return f"{usuario[:2]}***@{dominio}"


# ---------------------------------------------------------------------------
# Utilitários
# ---------------------------------------------------------------------------

def limpar(valor):
    """Converte ObjectId e estruturas aninhadas para exibição em tabela."""
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, dict):
        return {k: limpar(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [limpar(v) for v in valor]
    return valor


def tabela(docs):
    """Lista de documentos MongoDB -> DataFrame achatado e exibível."""
    docs = [limpar(d) for d in docs]
    if not docs:
        return pd.DataFrame()
    df = pd.json_normalize(docs)
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, (list, dict))).any():
            df[col] = df[col].map(lambda v: json.dumps(v, ensure_ascii=False, default=str)
                                  if isinstance(v, (list, dict)) else v)
    if "email" in df.columns:
        df["email"] = df["email"].map(mascarar_email)
    return df.drop(columns=[c for c in ("cpf_hash",) if c in df.columns])


def mostrar_pipeline(pipeline, titulo="Ver pipeline de agregação (MongoDB)"):
    with st.expander(titulo):
        st.code(json_util.dumps(pipeline, indent=2, ensure_ascii=False), language="json")


FORMATO = {c: st.column_config.NumberColumn(c, format="R$ %.2f")
           for c in ("preco", "preco_unitario", "subtotal", "receita", "valor_total", "frete", "faturamento")}


def num(n):
    """Inteiro com separador de milhar brasileiro."""
    return f"{n:,.0f}".replace(",", ".")


def preco_aleatorio(faixa):
    lo, hi = faixa
    valor = lo * (hi / lo) ** random.random()
    return round(max(round(valor) - 0.10, lo), 2)


def montar_entrega(cidade, uf, modalidade, cd_regional, rnd=random):
    """Calcula CD de origem, prazo previsto e frete conforme região e modalidade."""
    regiao = UF_REGIAO[uf]
    cd = CD_POR_REGIAO[regiao] if cd_regional else CD_CENTRAL
    if modalidade == "Entrega em casa":
        prazo = PRAZO_BASE[regiao] + rnd.randint(0, 1)
        frete = FRETE_BASE[regiao]
    else:
        prazo = 1 + rnd.randint(0, 1)
        frete = 0.0
    if not cd_regional:
        prazo += PRAZO_EXTRA_CENTRAL[regiao]
        frete *= 1.4
    return {
        "cidade": cidade, "estado": uf, "regiao": regiao, "modalidade": modalidade,
        "cd_origem": cd, "cd_regional": cd == CD_POR_REGIAO[regiao],
        "prazo_previsto_dias": prazo, "prazo_real_dias": None,
    }, round(frete, 2)


def buscar_clientes(db, termo, limite=30):
    filtro = {"nome": {"$regex": re.escape(termo), "$options": "i"}} if termo else {}
    return list(db.clientes.find(filtro, {"cpf_hash": 0}).sort("nome", 1).limit(limite))


def buscar_produtos(db, termo="", categoria=None, limite=50):
    filtro = {}
    if termo:
        filtro["nome"] = {"$regex": re.escape(termo), "$options": "i"}
    if categoria:
        filtro["categoria"] = categoria
    return list(db.produtos.find(filtro).sort("nome", 1).limit(limite))


def rotulo_cliente(c):
    return f"{c['nome']} | {c.get('cidade', '?')}/{c.get('estado', '?')} | {c.get('cpf_mascarado', '')}"


def rotulo_produto(p):
    return f"{p['nome']} ({p['categoria']}) {moeda(p['preco'])}"


# ---------------------------------------------------------------------------
# Geração de massa de dados (Faker pt_BR)
# ---------------------------------------------------------------------------

def gerar_clientes(db, n, fake):
    pesos = [c[2] for c in CIDADES]
    docs = []
    for _ in range(n):
        cidade, uf, _ = random.choices(CIDADES, weights=pesos)[0]
        cpf = fake.cpf()
        docs.append({
            "nome": fake.name(),
            "cpf_hash": hash_cpf(cpf),
            "cpf_mascarado": mascarar_cpf(cpf),
            "email": fake.free_email(),
            "cidade": cidade, "estado": uf, "regiao": UF_REGIAO[uf],
            "data_cadastro": fake.date_time_between(start_date="-5y", end_date="-200d"),
            "consentimento_marketing": random.random() < 0.7,
        })
    return inserir_em_lotes(db.clientes, docs)


def gerar_produtos(db, n):
    docs, nomes = [], set(db.produtos.distinct("nome"))
    for _ in range(n):
        categoria = random.choice(CATEGORIAS)
        tipos, marcas, faixa = CATALOGO[categoria]
        estoque = []
        for cd in CDS:
            if cd == CD_CENTRAL:
                qtd = random.randint(50, 500)
            else:
                chance_zero = 0.30 if cd == "CD Manaus-AM" else 0.15
                qtd = 0 if random.random() < chance_zero else random.randint(1, 120)
            estoque.append({"cd": cd, "quantidade": qtd})
        nome = f"{random.choice(tipos)} {random.choice(marcas)} {random.choice(VARIANTES)}"
        if nome in nomes:  # evita SKUs com nome repetido; se esgotar as combinações, numera
            nome = f"{nome} {len(nomes) + 1}"
        nomes.add(nome)
        docs.append({
            "nome": nome,
            "categoria": categoria,
            "preco": preco_aleatorio(faixa),
            "estoque": estoque,
            "ativo": True,
        })
    return inserir_em_lotes(db.produtos, docs)


def gerar_pedidos(db, n, dias=180, progresso=None):
    clientes = list(db.clientes.aggregate([
        {"$sample": {"size": 20000}},
        {"$project": {"cidade": 1, "estado": 1}},
    ]))
    produtos = list(db.produtos.find({}, {"preco": 1, "categoria": 1}))
    if not clientes or not produtos:
        raise ValueError("Cadastre clientes e produtos antes de gerar pedidos.")

    # Popularidade em cauda longa: poucos produtos vendem muito (efeito Pareto)
    random.shuffle(produtos)
    peso_produto = [1 / (i + 1) ** 0.8 for i in range(len(produtos))]
    por_categoria = {}
    for p, w in zip(produtos, peso_produto):
        lista = por_categoria.setdefault(p["categoria"], ([], []))
        lista[0].append(p)
        lista[1].append(w)

    agora = datetime.now().replace(microsecond=0)
    docs, inseridos = [], 0
    for i in range(n):
        cli = random.choice(clientes)
        regiao = UF_REGIAO[cli["estado"]]
        # Cada cliente tem categorias preferidas estáveis (base do motor de recomendação)
        favoritas = random.Random(str(cli["_id"])).sample(CATEGORIAS, 2)

        itens, usados = [], set()
        for _ in range(random.choices([1, 2, 3, 4], weights=[45, 30, 15, 10])[0]):
            cat = random.choice(favoritas) if random.random() < 0.75 else random.choice(CATEGORIAS)
            if cat not in por_categoria:
                continue
            p = random.choices(*por_categoria[cat])[0]
            if p["_id"] in usados:
                continue
            usados.add(p["_id"])
            itens.append({"produto_id": p["_id"], "quantidade": random.choices([1, 2, 3], weights=[80, 15, 5])[0],
                          "preco_unitario": p["preco"]})
        if not itens:
            continue

        canal = random.choices(CANAIS, weights=[50, 40, 10])[0]
        if canal == "Loja física":
            modalidade = "Retirada em loja"
        else:
            modalidade = random.choices(MODALIDADES, weights=[78, 12, 10])[0]
        cd_regional = random.random() < 0.72
        entrega, frete = montar_entrega(cli["cidade"], cli["estado"], modalidade, cd_regional)

        data = agora - timedelta(days=random.random() * dias)
        dias_passados = (agora - data).days
        if dias_passados < entrega["prazo_previsto_dias"]:
            status = "Processando" if dias_passados < 1 else "Em trânsito"
        else:
            status = "Cancelado" if random.random() < 0.05 else "Entregue"
        if status == "Entregue":
            chance = CHANCE_ATRASO[regiao] + (0 if entrega["cd_regional"] else 0.12)
            atraso = random.randint(1, 8 if regiao == "Norte" else 4) if random.random() < chance else 0
            entrega["prazo_real_dias"] = max(entrega["prazo_previsto_dias"] - random.randint(0, 1), 1) + atraso

        subtotal = sum(it["quantidade"] * it["preco_unitario"] for it in itens)
        docs.append({
            "cliente_id": cli["_id"], "data": data, "canal": canal, "status": status,
            "itens": itens, "frete": frete, "valor_total": round(subtotal + frete, 2), "entrega": entrega,
        })
        if len(docs) >= 5000:
            inseridos += inserir_em_lotes(db.pedidos, docs)
            docs = []
            if progresso:
                progresso.progress(min((i + 1) / n, 1.0), text=f"Pedidos: {num(i + 1)} de {num(n)}")
    inseridos += inserir_em_lotes(db.pedidos, docs)
    return inseridos


def inserir_em_lotes(colecao, docs, tamanho=5000):
    total = 0
    for i in range(0, len(docs), tamanho):
        try:
            total += len(colecao.insert_many(docs[i:i + tamanho], ordered=False).inserted_ids)
        except BulkWriteError as e:  # duplicidades (ex.: CPF repetido) são ignoradas
            total += e.details.get("nInserted", 0)
    return total


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

def pagina_inicio(db):
    st.title("🛒 E-Shop Brasil | Central de Dados")
    st.markdown(
        "Ambiente de simulação da equipe de TI da **E-Shop Brasil** (5 milhões de clientes, 100 mil pedidos/dia). "
        "Os dados ficam no **MongoDB**, rodando em **Docker**, e esta interface em **Streamlit** permite inserir, "
        "editar, concatenar e analisar o volume de dados para apoiar marketing, vendas e logística."
    )
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Clientes", num(db.clientes.estimated_document_count()))
    c2.metric("Produtos", num(db.produtos.estimated_document_count()))
    c3.metric("Pedidos", num(db.pedidos.estimated_document_count()))
    c4.metric("Visão unificada", num(db.visao_pedidos.estimated_document_count()))

    if db.pedidos.estimated_document_count() == 0:
        st.info("Banco vazio. Vá em **Inserir dados > Gerar massa de dados** para popular o MongoDB.")

    st.subheader("Como os dados estão organizados")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(
            "- **clientes**: dados cadastrais com CPF pseudonimizado (hash) e consentimento de marketing (LGPD)\n"
            "- **produtos**: catálogo com estoque por centro de distribuição (array embutido)\n"
            "- **pedidos**: itens embutidos + subdocumento de entrega (região, CD de origem, prazos)\n"
            "- **visao_pedidos**: coleção materializada com a junção das três coleções"
        )
    with col_b:
        exemplo = db.pedidos.find_one({}, {"_id": 0})
        if exemplo:
            st.caption("Exemplo de documento da coleção pedidos")
            st.json(json.loads(json_util.dumps(exemplo)), expanded=True)

    st.subheader("Índices criados")
    linhas = []
    for nome in ("clientes", "produtos", "pedidos"):
        for idx in db[nome].list_indexes():
            linhas.append({"coleção": nome, "índice": idx["name"], "campos": ", ".join(idx["key"].keys()),
                           "único": bool(idx.get("unique"))})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, column_config=FORMATO, use_container_width=True)


# --- Inserir ---------------------------------------------------------------

def pagina_inserir(db):
    st.title("Inserir dados")
    aba_gerar, aba_manual, aba_csv = st.tabs(["Gerar massa de dados (Faker)", "Cadastro manual", "Importar CSV"])

    with aba_gerar:
        st.markdown("Gera dados falsos realistas em português (Faker `pt_BR`) e insere em lotes de 5 mil documentos.")
        c1, c2, c3 = st.columns(3)
        n_cli = c1.number_input("Clientes", 0, 200_000, 3000, step=1000)
        n_prod = c2.number_input("Produtos", 0, 20_000, 400, step=100)
        n_ped = c3.number_input("Pedidos (últimos 180 dias)", 0, 500_000, 30_000, step=5000)
        if st.button("Gerar e inserir no MongoDB", type="primary"):
            fake = Faker("pt_BR")
            inicio = time.perf_counter()
            barra = st.progress(0.0, text="Gerando clientes...")
            qc = gerar_clientes(db, int(n_cli), fake) if n_cli else 0
            barra.progress(0.1, text="Gerando produtos...")
            qp = gerar_produtos(db, int(n_prod)) if n_prod else 0
            barra.progress(0.15, text="Gerando pedidos...")
            try:
                qo = gerar_pedidos(db, int(n_ped), progresso=barra) if n_ped else 0
            except ValueError as e:
                st.error(str(e))
                qo = 0
            barra.progress(1.0, text="Concluído")
            dur = time.perf_counter() - inicio
            total = qc + qp + qo
            st.success(f"Inseridos {num(qc)} clientes, {num(qp)} produtos e {num(qo)} pedidos em {dur:.1f}s "
                       f"({num(total / max(dur, 0.01))} documentos/s).")

        with st.expander("Zerar banco de dados"):
            st.warning("Apaga todas as coleções da base `eshop_brasil`.")
            if st.checkbox("Confirmo que quero apagar tudo") and st.button("Apagar tudo"):
                for nome in ("clientes", "produtos", "pedidos", "visao_pedidos"):
                    db[nome].delete_many({})
                st.success("Coleções esvaziadas.")

    with aba_manual:
        tipo = st.radio("O que cadastrar?", ["Cliente", "Produto", "Pedido"], horizontal=True)
        if tipo == "Cliente":
            form_cliente(db)
        elif tipo == "Produto":
            form_produto(db)
        else:
            form_pedido(db)

    with aba_csv:
        importar_csv(db)


def form_cliente(db):
    with st.form("novo_cliente", clear_on_submit=True):
        c1, c2 = st.columns(2)
        nome = c1.text_input("Nome completo")
        cpf = c2.text_input("CPF", placeholder="000.000.000-00")
        email = c1.text_input("E-mail")
        cidade_uf = c2.selectbox("Cidade", [f"{c}/{uf}" for c, uf, _ in CIDADES])
        consentimento = st.checkbox("Cliente consente em receber ofertas personalizadas (LGPD, art. 7º, I)")
        if st.form_submit_button("Cadastrar cliente", type="primary"):
            if not nome or len(so_digitos(cpf)) != 11:
                st.error("Informe nome e um CPF com 11 dígitos.")
                return
            cidade, uf = cidade_uf.rsplit("/", 1)
            try:
                res = db.clientes.insert_one({
                    "nome": nome.strip(), "cpf_hash": hash_cpf(cpf), "cpf_mascarado": mascarar_cpf(cpf),
                    "email": email.strip() or None, "cidade": cidade, "estado": uf, "regiao": UF_REGIAO[uf],
                    "data_cadastro": datetime.now().replace(microsecond=0), "consentimento_marketing": consentimento,
                })
                st.success(f"Cliente cadastrado com _id {res.inserted_id}. O CPF foi gravado apenas como hash.")
            except PyMongoError as e:
                st.error(f"Não foi possível cadastrar (CPF já existe?): {e}")


def form_produto(db):
    with st.form("novo_produto", clear_on_submit=True):
        c1, c2, c3 = st.columns([3, 2, 1])
        nome = c1.text_input("Nome do produto")
        categoria = c2.selectbox("Categoria", CATEGORIAS)
        preco = c3.number_input("Preço (R$)", 0.0, 100_000.0, 99.90, step=1.0)
        st.caption("Estoque por centro de distribuição")
        cols = st.columns(len(CDS))
        estoque = [{"cd": cd, "quantidade": int(col.number_input(cd.replace("CD ", ""), 0, 100_000, 10, key=f"est_{cd}"))}
                   for cd, col in zip(CDS, cols)]
        if st.form_submit_button("Cadastrar produto", type="primary"):
            if not nome:
                st.error("Informe o nome do produto.")
                return
            res = db.produtos.insert_one({"nome": nome.strip(), "categoria": categoria, "preco": round(preco, 2),
                                          "estoque": estoque, "ativo": True})
            st.success(f"Produto cadastrado com _id {res.inserted_id}.")


def form_pedido(db):
    termo = st.text_input("Buscar cliente pelo nome", key="ped_busca_cli")
    clientes = buscar_clientes(db, termo)
    if not clientes:
        st.info("Nenhum cliente encontrado.")
        return
    cliente = st.selectbox("Cliente", clientes, format_func=rotulo_cliente)

    c1, c2 = st.columns(2)
    categoria = c1.selectbox("Categoria dos produtos", CATEGORIAS)
    termo_prod = c2.text_input("Filtrar produto pelo nome")
    produtos = buscar_produtos(db, termo_prod, categoria, limite=100)
    por_id = {str(p["_id"]): p for p in produtos}
    ids = st.multiselect("Produtos", list(por_id), format_func=lambda i: rotulo_produto(por_id[i]))
    escolhidos = [por_id[i] for i in ids]
    qtds = {p["_id"]: st.number_input(f"Quantidade: {p['nome']}", 1, 50, 1, key=f"qtd_{p['_id']}") for p in escolhidos}

    c1, c2 = st.columns(2)
    canal = c1.selectbox("Canal", CANAIS)
    modalidade = c2.selectbox("Modalidade de entrega", MODALIDADES)

    if st.button("Registrar pedido", type="primary", disabled=not escolhidos):
        regiao = UF_REGIAO[cliente["estado"]]
        cd_regional = CD_POR_REGIAO[regiao]
        # Só sai do CD da região se todos os itens tiverem estoque lá; senão vai do CD central
        tem_estoque = all(
            next((e["quantidade"] for e in p["estoque"] if e["cd"] == cd_regional), 0) >= qtds[p["_id"]]
            for p in escolhidos
        )
        entrega, frete = montar_entrega(cliente["cidade"], cliente["estado"], modalidade, tem_estoque)
        itens = [{"produto_id": p["_id"], "quantidade": qtds[p["_id"]], "preco_unitario": p["preco"]} for p in escolhidos]
        subtotal = sum(i["quantidade"] * i["preco_unitario"] for i in itens)
        res = db.pedidos.insert_one({
            "cliente_id": cliente["_id"], "data": datetime.now().replace(microsecond=0), "canal": canal,
            "status": "Processando", "itens": itens, "frete": frete, "valor_total": round(subtotal + frete, 2),
            "entrega": entrega,
        })
        # Baixa de estoque no CD de origem com o operador posicional $
        for it in itens:
            db.produtos.update_one({"_id": it["produto_id"], "estoque.cd": entrega["cd_origem"]},
                                   {"$inc": {"estoque.$.quantidade": -it["quantidade"]}})
        st.success(f"Pedido {res.inserted_id} registrado: {moeda(subtotal + frete)}, sai do {entrega['cd_origem']} "
                   f"com prazo previsto de {entrega['prazo_previsto_dias']} dia(s).")


def importar_csv(db):
    st.markdown("Importe dados reais ou de parceiros (ex.: datasets do Kaggle). Cada linha vira um documento.")
    destino = st.selectbox("Coleção de destino", ["produtos", "clientes"])
    arquivo = st.file_uploader("Arquivo CSV", type="csv")
    if destino == "produtos":
        st.caption("Colunas esperadas: nome, categoria, preco (e opcionalmente estoque). "
                   "Há um exemplo em `dados/produtos_parceiro.csv`.")
    else:
        st.caption("Colunas esperadas: nome, cpf, email, cidade, estado. O CPF é convertido em hash antes de gravar.")
    if not arquivo:
        return
    df = pd.read_csv(arquivo)
    st.dataframe(df.head(20), hide_index=True, column_config=FORMATO, use_container_width=True)
    st.caption(f"{len(df)} linhas lidas.")
    if st.button(f"Inserir {len(df)} documentos em `{destino}`", type="primary"):
        docs = df.where(pd.notna(df), None).to_dict("records")
        if destino == "clientes":
            for d in docs:
                cpf = d.pop("cpf", None)
                if cpf:
                    d["cpf_hash"], d["cpf_mascarado"] = hash_cpf(cpf), mascarar_cpf(cpf)
                d["regiao"] = UF_REGIAO.get(str(d.get("estado", "")).upper())
                d["data_cadastro"] = datetime.now().replace(microsecond=0)
                d.setdefault("consentimento_marketing", False)
        else:
            for d in docs:
                d["preco"] = float(d.get("preco") or 0)
                qtd = int(d.pop("estoque", 0) or 0)
                d["estoque"] = [{"cd": cd, "quantidade": qtd if cd == CD_CENTRAL else 0} for cd in CDS]
                d["ativo"] = True
        st.success(f"{inserir_em_lotes(db[destino], docs)} documentos inseridos em `{destino}`.")


# --- Editar / Excluir ------------------------------------------------------

def pagina_editar(db):
    st.title("Editar ou excluir dados")
    aba_um, aba_lote = st.tabs(["Um documento por vez", "Ações em lote"])
    with aba_um:
        colecao = st.radio("Coleção", ["Clientes", "Produtos", "Pedidos"], horizontal=True)
        if colecao == "Clientes":
            editar_cliente(db)
        elif colecao == "Produtos":
            editar_produto(db)
        else:
            editar_pedido(db)
    with aba_lote:
        acoes_em_lote(db)


def editar_cliente(db):
    clientes = buscar_clientes(db, st.text_input("Buscar cliente pelo nome", key="ed_cli"))
    if not clientes:
        st.info("Nenhum cliente encontrado.")
        return
    c = st.selectbox("Selecione", clientes, format_func=rotulo_cliente)
    with st.form(f"form_cli_{c['_id']}"):
        col1, col2 = st.columns(2)
        nome = col1.text_input("Nome", c["nome"])
        email = col2.text_input("E-mail", c.get("email") or "")
        opcoes = [f"{ci}/{uf}" for ci, uf, _ in CIDADES]
        atual = f"{c.get('cidade')}/{c.get('estado')}"
        cidade_uf = col1.selectbox("Cidade", opcoes, index=opcoes.index(atual) if atual in opcoes else 0)
        consentimento = col2.checkbox("Consentimento de marketing", c.get("consentimento_marketing", False))
        if st.form_submit_button("Salvar alterações", type="primary"):
            cidade, uf = cidade_uf.rsplit("/", 1)
            db.clientes.update_one({"_id": c["_id"]}, {"$set": {
                "nome": nome, "email": email or None, "cidade": cidade, "estado": uf, "regiao": UF_REGIAO[uf],
                "consentimento_marketing": consentimento}})
            st.success("Cliente atualizado.")

    n_pedidos = db.pedidos.count_documents({"cliente_id": c["_id"]})
    st.markdown(f"**Direitos do titular (LGPD).** Este cliente tem {n_pedidos} pedido(s).")
    col1, col2 = st.columns(2)
    with col1:
        st.caption("Anonimizar: remove os dados pessoais e mantém os pedidos para fins fiscais e estatísticos.")
        if st.button("Anonimizar cliente"):
            db.clientes.update_one({"_id": c["_id"]}, {
                "$set": {"nome": "Titular anonimizado", "email": None, "consentimento_marketing": False,
                         "cpf_mascarado": "***.***.***-**", "anonimizado_em": datetime.now()},
                "$unset": {"cpf_hash": ""}})
            st.success("Dados pessoais removidos.")
    with col2:
        st.caption("Excluir: apaga o cliente e todos os pedidos dele.")
        confirma = st.checkbox("Confirmo a exclusão", key=f"conf_cli_{c['_id']}")
        if st.button("Excluir cliente", disabled=not confirma):
            r = db.pedidos.delete_many({"cliente_id": c["_id"]})
            db.clientes.delete_one({"_id": c["_id"]})
            st.success(f"Cliente excluído junto com {r.deleted_count} pedido(s).")


def editar_produto(db):
    c1, c2 = st.columns(2)
    termo = c1.text_input("Buscar produto pelo nome", key="ed_prod")
    categoria = c2.selectbox("Categoria", ["Todas"] + CATEGORIAS, key="ed_prod_cat")
    produtos = buscar_produtos(db, termo, None if categoria == "Todas" else categoria)
    if not produtos:
        st.info("Nenhum produto encontrado.")
        return
    p = st.selectbox("Selecione", produtos, format_func=rotulo_produto)
    with st.form(f"form_prod_{p['_id']}"):
        col1, col2, col3 = st.columns([3, 2, 1])
        nome = col1.text_input("Nome", p["nome"])
        categoria = col2.selectbox("Categoria", CATEGORIAS, index=CATEGORIAS.index(p["categoria"])
                                   if p["categoria"] in CATEGORIAS else 0)
        preco = col3.number_input("Preço (R$)", 0.0, 100_000.0, float(p["preco"]), step=1.0)
        st.caption("Estoque por centro de distribuição")
        estoque = st.data_editor(pd.DataFrame(p.get("estoque", [])), hide_index=True, disabled=["cd"],
                                 use_container_width=True)
        if st.form_submit_button("Salvar alterações", type="primary"):
            db.produtos.update_one({"_id": p["_id"]}, {"$set": {
                "nome": nome, "categoria": categoria, "preco": round(preco, 2),
                "estoque": [{"cd": r["cd"], "quantidade": int(r["quantidade"])} for r in estoque.to_dict("records")]}})
            st.success("Produto atualizado.")

    vendas = db.pedidos.count_documents({"itens.produto_id": p["_id"]})
    confirma = st.checkbox(f"Confirmo a exclusão (o produto aparece em {vendas} pedido(s))", key=f"conf_p_{p['_id']}")
    if st.button("Excluir produto", disabled=not confirma):
        db.produtos.delete_one({"_id": p["_id"]})
        st.success("Produto excluído.")


def editar_pedido(db):
    c1, c2 = st.columns(2)
    codigo = c1.text_input("Código do pedido (_id)", key="ed_ped")
    status = c2.selectbox("Ou listar os mais recentes com status", STATUS, index=1)
    if codigo:
        try:
            pedidos = list(db.pedidos.find({"_id": ObjectId(codigo.strip())}))
        except InvalidId:
            st.error("Código inválido.")
            return
    else:
        pedidos = list(db.pedidos.find({"status": status}).sort("data", -1).limit(50))
    if not pedidos:
        st.info("Nenhum pedido encontrado.")
        return
    ped = st.selectbox("Selecione", pedidos, format_func=lambda d: (
        f"{d['_id']} | {d['data']:%d/%m/%Y} | {d['entrega']['cidade']}/{d['entrega']['estado']} | "
        f"R$ {d['valor_total']:.2f} | {d['status']}"))
    st.dataframe(tabela([ped]), hide_index=True, column_config=FORMATO, use_container_width=True)

    with st.form(f"form_ped_{ped['_id']}"):
        col1, col2 = st.columns(2)
        novo_status = col1.selectbox("Status", STATUS, index=STATUS.index(ped["status"]))
        prazo_real = col2.number_input("Prazo real de entrega (dias)", 0, 120,
                                       int(ped["entrega"].get("prazo_real_dias") or ped["entrega"]["prazo_previsto_dias"]))
        if st.form_submit_button("Salvar alterações", type="primary"):
            db.pedidos.update_one({"_id": ped["_id"]}, {"$set": {
                "status": novo_status,
                "entrega.prazo_real_dias": prazo_real if novo_status == "Entregue" else None}})
            st.success("Pedido atualizado.")

    confirma = st.checkbox("Confirmo a exclusão do pedido", key=f"conf_ped_{ped['_id']}")
    if st.button("Excluir pedido", disabled=not confirma):
        db.pedidos.delete_one({"_id": ped["_id"]})
        st.success("Pedido excluído.")


def acoes_em_lote(db):
    st.subheader("Reajuste de preço por categoria")
    c1, c2 = st.columns(2)
    categoria = c1.selectbox("Categoria", CATEGORIAS, key="lote_cat")
    pct = c2.number_input("Reajuste (%)", -90.0, 200.0, 5.0, step=1.0)
    if st.button("Aplicar reajuste"):
        r = db.produtos.update_many({"categoria": categoria},
                                    [{"$set": {"preco": {"$round": [{"$multiply": ["$preco", 1 + pct / 100]}, 2]}}}])
        st.success(f"{r.modified_count} produto(s) de {categoria} reajustados em {pct:+.1f}%.")

    st.subheader("Limpeza de pedidos cancelados")
    n = db.pedidos.count_documents({"status": "Cancelado"})
    st.caption(f"Existem {num(n)} pedidos cancelados.")
    confirma = st.checkbox("Confirmo a exclusão dos pedidos cancelados")
    if st.button("Excluir cancelados", disabled=not confirma or n == 0):
        r = db.pedidos.delete_many({"status": "Cancelado"})
        st.success(f"{r.deleted_count} pedido(s) excluídos.")

    st.subheader("Repor estoque zerado")
    cd = st.selectbox("Centro de distribuição", CDS)
    qtd = st.number_input("Quantidade de reposição", 1, 10_000, 50)
    if st.button("Repor itens zerados neste CD"):
        r = db.produtos.update_many({"estoque": {"$elemMatch": {"cd": cd, "quantidade": {"$lte": 0}}}},
                                    {"$set": {"estoque.$[e].quantidade": qtd}},
                                    array_filters=[{"e.cd": cd, "e.quantidade": {"$lte": 0}}])
        st.success(f"{r.modified_count} produto(s) reabastecidos no {cd}.")


# --- Concatenar ------------------------------------------------------------

def pipeline_visao(match=None, limite=None):
    """Junta pedidos + clientes + produtos em uma linha por item vendido."""
    pipeline = [{"$match": match or {}}, {"$sort": {"data": -1}}]
    if limite:
        pipeline.append({"$limit": limite})
    pipeline += [
        {"$lookup": {"from": "clientes", "localField": "cliente_id", "foreignField": "_id", "as": "cliente"}},
        {"$unwind": "$cliente"},
        {"$unwind": "$itens"},
        {"$lookup": {"from": "produtos", "localField": "itens.produto_id", "foreignField": "_id", "as": "produto"}},
        {"$unwind": "$produto"},
        {"$project": {
            "_id": 0, "pedido_id": {"$toString": "$_id"}, "data": 1, "canal": 1, "status": 1,
            "cliente": "$cliente.nome", "cpf": "$cliente.cpf_mascarado",
            "local_entrega": {"$concat": ["$entrega.cidade", "/", "$entrega.estado", " (", "$entrega.regiao", ")"]},
            "produto": "$produto.nome", "categoria": "$produto.categoria",
            "quantidade": "$itens.quantidade", "preco_unitario": "$itens.preco_unitario",
            "subtotal": {"$round": [{"$multiply": ["$itens.quantidade", "$itens.preco_unitario"]}, 2]},
            "modalidade": "$entrega.modalidade", "cd_origem": "$entrega.cd_origem",
        }},
    ]
    return pipeline


def pagina_concatenar(db):
    st.title("Concatenação de dados")
    aba_join, aba_canais, aba_catalogo = st.tabs([
        "Junção de coleções ($lookup)", "Canais online + loja física (pd.concat)", "Catálogo + parceiro (CSV)"])

    with aba_join:
        st.markdown("Une **pedidos**, **clientes** e **produtos** em uma visão única, uma linha por item vendido. "
                    "O campo `local_entrega` é montado com `$concat`.")
        c1, c2 = st.columns([3, 1])
        regioes = c1.multiselect("Regiões", REGIOES, default=REGIOES, key="join_reg")
        limite = c2.number_input("Pedidos mais recentes", 10, 5000, 200, step=50)
        pipeline = pipeline_visao({"entrega.regiao": {"$in": regioes}}, int(limite))
        inicio = time.perf_counter()
        df = tabela(db.pedidos.aggregate(pipeline))
        st.caption(f"{num(len(df))} linhas em {(time.perf_counter() - inicio) * 1000:.0f} ms")
        st.dataframe(df, hide_index=True, column_config=FORMATO, use_container_width=True, height=380)
        mostrar_pipeline(pipeline)
        col1, col2 = st.columns(2)
        col1.download_button("Baixar CSV", df.to_csv(index=False).encode("utf-8"), "visao_pedidos.csv", "text/csv",
                             disabled=df.empty)
        if col2.button("Materializar visão completa em `visao_pedidos` ($out)", type="primary"):
            inicio = time.perf_counter()
            db.pedidos.aggregate(pipeline_visao() + [{"$out": "visao_pedidos"}], allowDiskUse=True)
            st.success(f"{num(db.visao_pedidos.count_documents({}))} linhas gravadas em "
                       f"{time.perf_counter() - inicio:.1f}s. A coleção pode alimentar BI e relatórios sem "
                       f"refazer as junções.")

    with aba_canais:
        st.markdown("Simula duas fontes separadas, o **e-commerce** (site + app) e o **PDV das lojas físicas**, "
                    "e empilha as duas com `pd.concat` para uma visão omnichannel.")
        dias = st.slider("Período (últimos N dias)", 7, 180, 30)
        desde = datetime.now() - timedelta(days=dias)
        campos = {"_id": 1, "data": 1, "canal": 1, "valor_total": 1, "status": 1,
                  "entrega.modalidade": 1, "entrega.regiao": 1}
        online = tabela(db.pedidos.find({"data": {"$gte": desde}, "canal": {"$in": ["Site", "App"]}}, campos))
        loja = tabela(db.pedidos.find({"data": {"$gte": desde}, "canal": "Loja física"}, campos))
        if online.empty and loja.empty:
            st.info("Sem pedidos no período.")
        else:
            online["origem"], loja["origem"] = "E-commerce", "PDV loja física"
            unificado = pd.concat([online, loja], ignore_index=True)
            c1, c2, c3 = st.columns(3)
            c1.metric("Fonte 1: e-commerce", num(len(online)))
            c2.metric("Fonte 2: lojas físicas", num(len(loja)))
            c3.metric("Base unificada", num(len(unificado)))
            resumo = (unificado.groupby(["origem", "entrega.modalidade"])["valor_total"]
                      .agg(pedidos="count", faturamento="sum").reset_index())
            fig = px.bar(resumo, x="origem", y="pedidos", color="entrega.modalidade", barmode="stack",
                         labels={"entrega.modalidade": "Modalidade", "origem": "Origem"},
                         title="Pedidos por origem e modalidade de entrega")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(unificado.head(300), hide_index=True, column_config=FORMATO, use_container_width=True)

    with aba_catalogo:
        st.markdown("Concatena o **catálogo atual** com o catálogo de um **parceiro** (CSV), remove duplicados "
                    "pelo nome e permite inserir só os produtos novos.")
        arquivo = st.file_uploader("CSV do parceiro", type="csv", key="csv_parceiro")
        exemplo = PASTA_DADOS / "produtos_parceiro.csv"
        usar_exemplo = st.checkbox("Usar o arquivo de exemplo `dados/produtos_parceiro.csv`", value=not arquivo)
        if arquivo:
            parceiro = pd.read_csv(arquivo)
        elif usar_exemplo and exemplo.exists():
            parceiro = pd.read_csv(exemplo)
        else:
            return
        atual = tabela(db.produtos.find({}, {"_id": 0, "nome": 1, "categoria": 1, "preco": 1}))
        atual["origem"], parceiro["origem"] = "Catálogo E-Shop", "Parceiro"
        empilhado = pd.concat([atual, parceiro], ignore_index=True)
        empilhado["chave"] = empilhado["nome"].str.strip().str.lower()
        # Mantém a primeira ocorrência: o catálogo atual vem antes, então só sobram itens inéditos do parceiro
        novos = empilhado[~empilhado.duplicated("chave", keep="first") & (empilhado["origem"] == "Parceiro")]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Catálogo atual", len(atual))
        c2.metric("Linhas do parceiro", len(parceiro))
        c3.metric("Duplicados descartados", len(parceiro) - len(novos))
        c4.metric("Produtos novos", len(novos))
        st.dataframe(novos.drop(columns=["chave"]), hide_index=True, column_config=FORMATO, use_container_width=True)
        if st.button(f"Inserir {len(novos)} produto(s) novo(s)", type="primary", disabled=novos.empty):
            docs = []
            for r in novos.to_dict("records"):
                qtd = int(r.get("estoque") or 0) if pd.notna(r.get("estoque")) else 0
                docs.append({"nome": r["nome"], "categoria": r["categoria"], "preco": float(r["preco"]),
                             "estoque": [{"cd": cd, "quantidade": qtd if cd == CD_CENTRAL else 0} for cd in CDS],
                             "ativo": True, "fornecedor": "Parceiro"})
            st.success(f"{inserir_em_lotes(db.produtos, docs)} produto(s) inseridos.")


# --- Consultas -------------------------------------------------------------

def filtros_pedidos(db):
    limites = list(db.pedidos.aggregate([{"$group": {"_id": None, "min": {"$min": "$data"}, "max": {"$max": "$data"}}}]))
    if not limites:
        return None
    dmin, dmax = limites[0]["min"].date(), limites[0]["max"].date()
    c1, c2, c3 = st.columns([2, 3, 2])
    periodo = c1.date_input("Período", (max(dmin, dmax - timedelta(days=90)), dmax), min_value=dmin, max_value=dmax,
                            format="DD/MM/YYYY")
    regioes = c2.multiselect("Regiões", REGIOES, default=REGIOES)
    canais = c3.multiselect("Canais", CANAIS, default=CANAIS)
    st.caption("Os filtros acima valem para as abas Vendas e Logística.")
    ini, fim = (periodo if len(periodo) == 2 else (periodo[0], periodo[0]))
    return {
        "data": {"$gte": datetime.combine(ini, dtime.min), "$lt": datetime.combine(fim + timedelta(days=1), dtime.min)},
        "entrega.regiao": {"$in": regioes}, "canal": {"$in": canais},
    }


def pagina_consultas(db):
    st.title("Consultas e análises")
    filtro = filtros_pedidos(db)
    if filtro is None:
        st.info("Ainda não há pedidos. Gere dados na página **Inserir dados**.")
        return
    aba_vendas, aba_log, aba_pers, aba_livre = st.tabs(
        ["Vendas", "Logística e estoque", "Personalização", "Consulta livre"])
    with aba_vendas:
        analise_vendas(db, filtro)
    with aba_log:
        analise_logistica(db, filtro)
    with aba_pers:
        analise_personalizacao(db)
    with aba_livre:
        consulta_livre(db)


def analise_vendas(db, filtro):
    match = {"$match": {**filtro, "status": {"$ne": "Cancelado"}}}
    kpi = list(db.pedidos.aggregate([match, {"$group": {
        "_id": None, "pedidos": {"$sum": 1}, "faturamento": {"$sum": "$valor_total"}}}]))
    if not kpi:
        st.info("Nenhum pedido com esses filtros.")
        return
    kpi = kpi[0]
    clientes = next(db.pedidos.aggregate([match, {"$group": {"_id": "$cliente_id"}}, {"$count": "n"}]), {"n": 0})["n"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Pedidos", num(kpi['pedidos']))
    c2.metric("Faturamento", moeda_curta(kpi["faturamento"]))
    c3.metric("Ticket médio", moeda(kpi["faturamento"] / kpi["pedidos"]))
    c4.metric("Clientes únicos", num(clientes))

    diario = [match, {"$group": {"_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$data"}},
                                 "faturamento": {"$sum": "$valor_total"}, "pedidos": {"$sum": 1}}},
              {"$sort": {"_id": 1}}]
    df = pd.DataFrame(db.pedidos.aggregate(diario)).rename(columns={"_id": "dia"})
    st.plotly_chart(px.line(df, x="dia", y="faturamento", title="Faturamento diário (R$)"), use_container_width=True)
    mostrar_pipeline(diario)

    col1, col2 = st.columns(2)
    por_regiao = pd.DataFrame(db.pedidos.aggregate([match, {"$group": {
        "_id": "$entrega.regiao", "faturamento": {"$sum": "$valor_total"}, "pedidos": {"$sum": 1}}},
        {"$sort": {"faturamento": -1}}])).rename(columns={"_id": "região"})
    col1.plotly_chart(px.bar(por_regiao, x="região", y="faturamento", text_auto=".3s",
                             title="Faturamento por região"), use_container_width=True)
    por_canal = pd.DataFrame(db.pedidos.aggregate([match, {"$group": {"_id": "$canal", "pedidos": {"$sum": 1}}}]))
    col2.plotly_chart(px.pie(por_canal, names="_id", values="pedidos", hole=0.45, title="Pedidos por canal"),
                      use_container_width=True)

    por_categoria = [match, {"$unwind": "$itens"},
                     {"$lookup": {"from": "produtos", "localField": "itens.produto_id", "foreignField": "_id",
                                  "as": "p"}},
                     {"$unwind": "$p"},
                     {"$group": {"_id": "$p.categoria", "receita": {"$sum": {
                         "$multiply": ["$itens.quantidade", "$itens.preco_unitario"]}}}},
                     {"$sort": {"receita": -1}}]
    df_cat = pd.DataFrame(db.pedidos.aggregate(por_categoria)).rename(columns={"_id": "categoria"})
    col1.plotly_chart(px.bar(df_cat, x="receita", y="categoria", orientation="h", title="Receita por categoria"),
                      use_container_width=True)

    top = [match, {"$unwind": "$itens"},
           {"$group": {"_id": "$itens.produto_id", "unidades": {"$sum": "$itens.quantidade"},
                       "receita": {"$sum": {"$multiply": ["$itens.quantidade", "$itens.preco_unitario"]}}}},
           {"$sort": {"unidades": -1}}, {"$limit": 10},
           {"$lookup": {"from": "produtos", "localField": "_id", "foreignField": "_id", "as": "p"}},
           {"$unwind": "$p"},
           {"$project": {"_id": 0, "produto": "$p.nome", "categoria": "$p.categoria", "unidades": 1,
                         "receita": {"$round": ["$receita", 2]}}}]
    col2.markdown("**Top 10 produtos mais vendidos**")
    col2.dataframe(pd.DataFrame(db.pedidos.aggregate(top)), hide_index=True, column_config=FORMATO, use_container_width=True)
    mostrar_pipeline(top, "Ver pipeline do top 10")


def moeda(valor):
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def moeda_curta(valor):
    for limite, sufixo in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if abs(valor) >= limite:
            return f"R$ {valor / limite:.2f} {sufixo}".replace(".", ",")
    return moeda(valor)


def analise_logistica(db, filtro):
    entregues = {"$match": {**filtro, "status": "Entregue"}}
    prazos = [entregues, {"$group": {
        "_id": "$entrega.regiao",
        "prazo_previsto": {"$avg": "$entrega.prazo_previsto_dias"},
        "prazo_real": {"$avg": "$entrega.prazo_real_dias"},
        "atrasados": {"$sum": {"$cond": [{"$gt": ["$entrega.prazo_real_dias", "$entrega.prazo_previsto_dias"]}, 1, 0]}},
        "entregas": {"$sum": 1}}},
        {"$addFields": {"pct_atraso": {"$round": [{"$multiply": [{"$divide": ["$atrasados", "$entregas"]}, 100]}, 1]}}},
        {"$sort": {"prazo_real": -1}}]
    df = pd.DataFrame(db.pedidos.aggregate(prazos)).rename(columns={"_id": "região"})
    if df.empty:
        st.info("Nenhuma entrega concluída com esses filtros.")
        return
    col1, col2 = st.columns(2)
    longo = (df.rename(columns={"prazo_previsto": "Previsto", "prazo_real": "Real"})
             .melt(id_vars="região", value_vars=["Previsto", "Real"], var_name="prazo", value_name="dias"))
    col1.plotly_chart(px.bar(longo, x="região", y="dias", color="prazo", barmode="group", text_auto=".1f",
                             title="Prazo médio de entrega por região (dias)"), use_container_width=True)
    col2.plotly_chart(px.bar(df, x="região", y="pct_atraso", text_auto=True, color="pct_atraso",
                             color_continuous_scale="Reds", title="% de entregas atrasadas",
                             labels={"pct_atraso": "% atraso"}),
                      use_container_width=True)
    mostrar_pipeline(prazos)

    st.subheader("Efeito do centro de distribuição regional")
    cd = pd.DataFrame(db.pedidos.aggregate([entregues, {"$group": {
        "_id": {"regiao": "$entrega.regiao", "regional": "$entrega.cd_regional"},
        "prazo_real": {"$avg": "$entrega.prazo_real_dias"}, "frete": {"$avg": "$frete"}, "pedidos": {"$sum": 1}}}]))
    if not cd.empty:
        cd["região"] = cd["_id"].map(lambda k: k["regiao"])
        cd["origem"] = cd["_id"].map(lambda k: "CD da própria região" if k["regional"] else "CD central (Cajamar-SP)")
        cd = cd[cd["região"] != "Sudeste"]
        st.plotly_chart(px.bar(cd, x="região", y="prazo_real", color="origem", barmode="group", text_auto=".1f",
                               labels={"prazo_real": "dias"}, title="Prazo real médio (dias): CD regional x CD central"), use_container_width=True)
        st.caption("Pedidos atendidos pelo CD da própria região chegam dias antes e com frete menor. "
                   "Manter estoque regional é a principal alavanca para o Norte e o Nordeste.")

    col1, col2 = st.columns(2)
    modal = pd.DataFrame(db.pedidos.aggregate([{"$match": filtro}, {"$group": {
        "_id": "$entrega.modalidade", "pedidos": {"$sum": 1}}}]))
    col1.plotly_chart(px.pie(modal, names="_id", values="pedidos", hole=0.45,
                             title="Omnichannel: modalidades de entrega"), use_container_width=True)

    limite = col2.slider("Considerar ruptura quando o estoque for menor ou igual a", 0, 50, 5)
    ruptura = pd.DataFrame(db.produtos.aggregate([
        {"$unwind": "$estoque"}, {"$match": {"estoque.quantidade": {"$lte": limite}}},
        {"$group": {"_id": "$estoque.cd", "produtos": {"$sum": 1}}}, {"$sort": {"produtos": -1}}]))
    if not ruptura.empty:
        col2.plotly_chart(px.bar(ruptura, x="_id", y="produtos", labels={"_id": "CD"},
                                 title="Produtos em risco de ruptura por CD"), use_container_width=True)


def analise_personalizacao(db):
    st.subheader("Quem comprou este produto também comprou")
    mais_vendidos = list(db.pedidos.aggregate([
        {"$unwind": "$itens"}, {"$group": {"_id": "$itens.produto_id", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 200},
        {"$lookup": {"from": "produtos", "localField": "_id", "foreignField": "_id", "as": "p"}},
        {"$unwind": "$p"}, {"$replaceRoot": {"newRoot": "$p"}}]))
    if mais_vendidos:
        produto = st.selectbox("Produto", mais_vendidos, format_func=rotulo_produto)
        pid = produto["_id"]
        pipeline = [
            {"$match": {"itens.produto_id": pid}},
            {"$unwind": "$itens"},
            {"$match": {"itens.produto_id": {"$ne": pid}}},
            {"$group": {"_id": "$itens.produto_id", "pedidos_juntos": {"$sum": 1}}},
            {"$sort": {"pedidos_juntos": -1}}, {"$limit": 5},
            {"$lookup": {"from": "produtos", "localField": "_id", "foreignField": "_id", "as": "p"}},
            {"$unwind": "$p"},
            {"$project": {"_id": 0, "produto": "$p.nome", "categoria": "$p.categoria", "preco": "$p.preco",
                          "pedidos_juntos": 1}}]
        st.caption(f"{num(db.pedidos.count_documents({'itens.produto_id': pid}))} pedidos contêm este produto.")
        st.dataframe(pd.DataFrame(db.pedidos.aggregate(pipeline)), hide_index=True, column_config=FORMATO, use_container_width=True)
        mostrar_pipeline(pipeline)

    st.subheader("Recomendações para um cliente")
    clientes = buscar_clientes(db, st.text_input("Buscar cliente pelo nome", key="rec_cli"))
    if not clientes:
        st.info("Nenhum cliente encontrado.")
        return
    cliente = st.selectbox("Cliente", clientes, format_func=rotulo_cliente, key="rec_sel")
    historico = pd.DataFrame(db.pedidos.aggregate([
        {"$match": {"cliente_id": cliente["_id"]}}, {"$unwind": "$itens"},
        {"$lookup": {"from": "produtos", "localField": "itens.produto_id", "foreignField": "_id", "as": "p"}},
        {"$unwind": "$p"},
        {"$group": {"_id": "$p.categoria", "itens": {"$sum": "$itens.quantidade"},
                    "produtos": {"$addToSet": "$p._id"}}},
        {"$sort": {"itens": -1}}]))
    if historico.empty:
        st.info("Este cliente ainda não tem compras. Recomendação: produtos mais vendidos na região dele.")
        return
    if not cliente.get("consentimento_marketing"):
        st.warning("Cliente **sem consentimento** de marketing: as recomendações aparecem só na navegação do site, "
                   "sem envio de e-mail ou push (LGPD).")
    col1, col2 = st.columns([1, 2])
    col1.markdown("**Histórico por categoria**")
    col1.dataframe(historico[["_id", "itens"]].rename(columns={"_id": "categoria"}), hide_index=True, column_config=FORMATO)

    favoritas = historico["_id"].head(2).tolist()
    comprados = [pid for lista in historico["produtos"] for pid in lista]
    rec = [
        {"$match": {"entrega.regiao": cliente.get("regiao")}},
        {"$unwind": "$itens"},
        {"$match": {"itens.produto_id": {"$nin": comprados}}},
        {"$lookup": {"from": "produtos", "localField": "itens.produto_id", "foreignField": "_id", "as": "p"}},
        {"$unwind": "$p"},
        {"$match": {"p.categoria": {"$in": favoritas}}},
        {"$group": {"_id": "$p._id", "produto": {"$first": "$p.nome"}, "categoria": {"$first": "$p.categoria"},
                    "preco": {"$first": "$p.preco"}, "popularidade_na_regiao": {"$sum": 1}}},
        {"$sort": {"popularidade_na_regiao": -1}}, {"$limit": 5}, {"$project": {"_id": 0}}]
    col2.markdown(f"**Recomendados** (categorias favoritas: {', '.join(favoritas)}; mais vendidos na região "
                  f"{cliente.get('regiao')}; exclui o que já comprou)")
    col2.dataframe(pd.DataFrame(db.pedidos.aggregate(rec)), hide_index=True, column_config=FORMATO, use_container_width=True)
    mostrar_pipeline(rec)


def consulta_livre(db):
    st.markdown("Consulta direta ao MongoDB com filtro em JSON. O plano de execução mostra se a consulta "
                "usou índice (`IXSCAN`) ou varreu a coleção inteira (`COLLSCAN`).")
    c1, c2, c3 = st.columns([1, 3, 1])
    colecao = c1.selectbox("Coleção", ["pedidos", "clientes", "produtos", "visao_pedidos"])
    exemplos = {
        "pedidos": '{"entrega.regiao": "Norte", "status": "Entregue", "valor_total": {"$gt": 1000}}',
        "clientes": '{"estado": "AM", "consentimento_marketing": true}',
        "produtos": '{"categoria": "Eletrônicos", "preco": {"$lt": 300}}',
        "visao_pedidos": '{"categoria": "Livros", "modalidade": "Ponto de coleta"}',
    }
    texto = c2.text_area("Filtro (JSON)", exemplos[colecao], height=68, key=f"filtro_{colecao}")
    limite = c3.number_input("Limite", 1, 5000, 100)
    try:
        filtro = json_util.loads(texto or "{}")
    except (ValueError, TypeError) as e:
        st.error(f"JSON inválido: {e}")
        return
    try:
        inicio = time.perf_counter()
        docs = list(db[colecao].find(filtro).limit(int(limite)))
        ms = (time.perf_counter() - inicio) * 1000
        total = db[colecao].count_documents(filtro)
        plano = db[colecao].find(filtro).limit(int(limite)).explain()
    except PyMongoError as e:
        st.error(f"Erro na consulta: {e}")
        return
    plano_txt = json.dumps(plano.get("queryPlanner", {}).get("winningPlan", {}), default=str)
    estatisticas = plano.get("executionStats", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documentos que atendem", num(total))
    c2.metric("Tempo", f"{ms:.0f} ms")
    c3.metric("Estratégia do plano", "IXSCAN" if "IXSCAN" in plano_txt else "COLLSCAN",
              help="IXSCAN = usou índice; COLLSCAN = varreu a coleção inteira")
    c4.metric("Docs examinados", num(estatisticas.get('totalDocsExamined', 0)))
    st.dataframe(tabela(docs), hide_index=True, column_config=FORMATO, use_container_width=True)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

PAGINAS = {
    "Início": pagina_inicio,
    "Inserir dados": pagina_inserir,
    "Editar / Excluir": pagina_editar,
    "Concatenar": pagina_concatenar,
    "Consultas e análises": pagina_consultas,
}


def main():
    try:
        db = conectar()
    except PyMongoError as e:
        st.error(f"Não foi possível conectar ao MongoDB em `{MONGO_URI.split('@')[-1]}`: {e}")
        st.stop()
    with st.sidebar:
        st.header("E-Shop Brasil")
        pagina = st.radio("Navegação", list(PAGINAS), label_visibility="collapsed")
        st.divider()
        st.caption(f"MongoDB conectado: `{DB_NAME}`")
        st.caption("Dados pessoais exibidos de forma mascarada (LGPD).")
    PAGINAS[pagina](db)


main()

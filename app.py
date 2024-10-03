import os
import json
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore

app = Flask(__name__)
CORS(app)

# Carregar as credenciais do Firebase a partir da variável de ambiente
firebase_credentials = os.getenv('FIREBASE_CREDENTIALS')

if firebase_credentials is None:
    print("Credenciais do Firebase não encontradas. Verifique a configuração das variáveis de ambiente.")
else:
    cred = credentials.Certificate(json.loads(firebase_credentials))
    firebase_admin.initialize_app(cred)

db = firestore.client()

collection_name = 'PCD'

collections = db.collections()
collection_exists = any(collection.id == collection_name for collection in collections)

if collection_exists:
    # Recupera todos os documentos da coleção
    docs = db.collection(collection_name).get()

def get_jobs_from_firestore():
    jobs_ref = db.collection('PCD')
    docs = jobs_ref.stream()
    jobs = []
    for doc in docs:
        job = doc.to_dict()
        job['id'] = doc.id  
        jobs.append(job)
    return jobs

jobs = get_jobs_from_firestore()

for job in jobs:
    if 'descrição' not in job:
        print(f"Documento sem 'descrição': {job}")
    else:
        print(f"Descrição encontrada")

descriptions = [job['descrição'] for job in jobs if 'descrição' in job]
tfidf = TfidfVectorizer().fit_transform(descriptions)

# Função para encontrar o índice do trabalho pelo título
def find_job_index_by_title(description):
    for index, job in enumerate(jobs):
        if job.get('descrição', '').lower() == description.lower():
            return index
    return None

def find_job_index_by_similar_description(description):
    if not description:
        return None

    job_descriptions = [job.get('descrição', '') for job in jobs]
    job_descriptions.append(description)

    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix = tfidf_vectorizer.fit_transform(job_descriptions)

    cosine_similarities = linear_kernel(tfidf_matrix[-1:], tfidf_matrix[:-1]).flatten()

    most_similar_job_index = cosine_similarities.argmax()

    if cosine_similarities[most_similar_job_index] > 0.1:  # Limite de similaridade
        return most_similar_job_index

    return None

# Rota para recomendação de vagas
@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    job_title = data.get('trabalho')

    if job_title is None:
        return jsonify({"error": "O campo 'descrição' é necessário."}), 400

    print(f"Recebido título da vaga: {job_title}")

    job_index = find_job_index_by_similar_description(job_title)

    if job_index is None:
        return jsonify({"error": "Nenhuma vaga correspondente encontrada."}), 404

    cosine_similarities = linear_kernel(tfidf

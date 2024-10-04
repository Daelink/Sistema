import os
from flask import Flask, request, jsonify
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from flask_cors import CORS
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurar o Firebase
cred = credentials.Certificate({
    "type": os.getenv('FIREBASE_TYPE'),
    "project_id": os.getenv('FIREBASE_PROJECT_ID'),
    "private_key_id": os.getenv('FIREBASE_PRIVATE_KEY_ID'),
    "private_key": os.getenv('FIREBASE_PRIVATE_KEY').replace('\\n', '\n'),  # Corrige a quebra de linha
    "client_email": os.getenv('FIREBASE_CLIENT_EMAIL'),
    "client_id": os.getenv('FIREBASE_CLIENT_ID'),
    "auth_uri": os.getenv('FIREBASE_AUTH_URI'),
    "token_uri": os.getenv('FIREBASE_TOKEN_URI'),
    "auth_provider_x509_cert_url": os.getenv('FIREBASE_AUTH_PROVIDER_X509_CERT_URL'),
    "client_x509_cert_url": os.getenv('FIREBASE_CLIENT_X509_CERT_URL'),
    "universe_domain": os.getenv('FIREBASE_UNIVERSE_DOMAIN')
})

firebase_admin.initialize_app(cred)

db = firestore.client()

collection_name = 'PCD'

def get_jobs_from_firestore():
    jobs_ref = db.collection(collection_name)
    docs = jobs_ref.stream()
    jobs = []
    for doc in docs:
        job = doc.to_dict()
        job['id'] = doc.id  
        jobs.append(job)
    return jobs

jobs = get_jobs_from_firestore()

# Verificação das descrições
for job in jobs:
    if 'descrição' not in job:
        print(f"Documento sem 'descrição': {job}")
    else:
        print(f"Descrição encontrada")

descriptions = [job['descrição'] for job in jobs if 'descrição' in job]
tfidf = TfidfVectorizer().fit_transform(descriptions)

def find_job_index_by_similar_description(description):
    if not description:
        return None

    job_descriptions = [job.get('descrição', '') for job in jobs]
    job_descriptions.append(description)

    tfidf_vectorizer = TfidfVectorizer()
    tfidf_matrix = tfidf_vectorizer.fit_transform(job_descriptions)

    cosine_similarities = linear_kernel(tfidf_matrix[-1:], tfidf_matrix[:-1]).flatten()
    most_similar_job_index = cosine_similarities.argmax()

    if cosine_similarities[most_similar_job_index] > 0.1:  # Defina um limiar de similaridade
        return most_similar_job_index

    return None

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.json
    job_title = data.get('trabalho')

    if job_title is None:
        return jsonify({"error": "O campo 'trabalho' é necessário."}), 400

    print(f"Recebido título da vaga: {job_title}")

    job_index = find_job_index_by_similar_description(job_title)

    if job_index is None:
        return jsonify({"error": "Nenhuma vaga correspondente encontrada."}), 404

    cosine_similarities = linear_kernel(tfidf[job_index:job_index + 1], tfidf).flatten()
    related_docs_indices = cosine_similarities.argsort()[:-20:-1]

    recommendations = [jobs[i] for i in related_docs_indices if i != job_index]
    recommendations.insert(0, jobs[job_index])  # Colocar a vaga solicitada no início

    return jsonify(recommendations)

@app.route('/profile', methods=['POST'])
def recommend_profile():
    data = request.json
    job_id = data.get('id')

    print(f"Recebido ID da vaga: {job_id}")

    job_index = next((index for (index, job) in enumerate(jobs) if job["id"] == job_id), None)

    if job_index is None:
        return jsonify({"error": "Nenhuma vaga encontrada com o ID fornecido."}), 404

    cosine_similarities = linear_kernel(tfidf[job_index:job_index + 1], tfidf).flatten()
    related_docs_indices = cosine_similarities.argsort()[:-5:-1]

    recommendations = [jobs[i] for i in related_docs_indices if i != job_index]
    recommendations.insert(0, jobs[job_index])  # Colocar a vaga solicitada no início

    return jsonify(recommendations)

if __name__ == '__main__':
    app.run(debug=True)

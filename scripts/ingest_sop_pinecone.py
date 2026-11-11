"""Optional vector ingestion. Never deletes indexes or documents in existing namespaces."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    import os
    import time
    from dotenv import load_dotenv
    from pinecone import Pinecone, ServerlessSpec
    from langchain_pinecone import PineconeVectorStore
    from langchain_core.documents import Document
    from src.retrieval import ROOT, load_chunks, policy_namespace
    load_dotenv(ROOT / '.env')
    if not os.getenv('PINECONE_API_KEY'):
        raise ValueError('Set PINECONE_API_KEY; local retrieval does not need this script.')
    mode = os.getenv('Embeddings_model', 'OPENAI').upper()
    if mode == 'OPENAI':
        from langchain_openai import OpenAIEmbeddings
        embedding = OpenAIEmbeddings()
        index_name = 'fde-sop-index-openai'
    else:
        from langchain_huggingface import HuggingFaceEmbeddings
        embedding = HuggingFaceEmbeddings(model_name=os.getenv('Local_Embedding_Model', 'BAAI/bge-m3'))
        index_name = 'fde-sop-index-local'
    dimension = len(embedding.embed_query('dimension check'))
    pc = Pinecone(api_key=os.environ['PINECONE_API_KEY'])
    if index_name in pc.list_indexes().names():
        if pc.describe_index(index_name).dimension != dimension:
            raise ValueError('Index dimension mismatch. Migrate explicitly; no index was deleted.')
    else:
        pc.create_index(name=index_name, dimension=dimension, metric='cosine',
                        spec=ServerlessSpec(cloud='aws', region='us-east-1'))
    deadline = time.monotonic() + 45
    while not pc.describe_index(index_name).status['ready']:
        if time.monotonic() > deadline:
            raise TimeoutError('Index not ready. Retry ingestion later.')
        time.sleep(1)
    # Content-specific namespaces keep removed/stale chunks out of retrieval.
    namespace = policy_namespace()
    store = PineconeVectorStore(index_name=index_name, embedding=embedding, namespace=namespace)
    chunks = load_chunks(str(ROOT / 'data/policy'))
    if not chunks:
        raise ValueError('No policy text found.')
    documents = [Document(page_content=c['text'], metadata={'source_file': c['source'],
                  'section': c['section'], 'chunk_id': c['id']}) for c in chunks]
    for offset in range(0, len(documents), 50):
        store.add_documents(documents[offset:offset+50], ids=[c['id'] for c in chunks[offset:offset+50]])
    print(f'Uploaded {len(documents)} chunks into {index_name}, namespace {namespace}.')
    print('Wait for Pinecone eventual consistency before querying. Old namespaces are retained for manual cleanup.')


if __name__ == '__main__':
    main()

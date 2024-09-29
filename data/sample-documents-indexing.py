from dotenv import load_dotenv
load_dotenv()

import os
import pandas as pd
from azure.identity import get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswParameters,
    HnswAlgorithmConfiguration,
    SemanticPrioritizedFields,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticSearch,
    SemanticConfiguration,
    SemanticField,
    SimpleField,
    VectorSearch,
    VectorSearchAlgorithmKind,
    VectorSearchAlgorithmMetric,
    ExhaustiveKnnAlgorithmConfiguration,
    ExhaustiveKnnParameters,
    VectorSearchProfile,
)
from typing import List, Dict
from openai import AzureOpenAI

from azure_config import AzureConfig 

# Initialize AzureConfig
azure_config = AzureConfig()

def delete_index(search_index_client: SearchIndexClient, search_index: str):
    print(f"deleting index {search_index}")
    search_index_client.delete_index(search_index)

def create_index_definition(name: str) -> SearchIndex:
    """
    Returns an Azure Cognitive Search index with the given name.
    """
    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="filepath", type=SearchFieldDataType.String),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SimpleField(name="url", type=SearchFieldDataType.String),
        SearchField(
            name="contentVector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            vector_search_dimensions=1536,
            vector_search_profile_name="myHnswProfile",
        ),
    ]

    semantic_config = SemanticConfiguration(
        name="default",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="title"),
            keywords_fields=[],
            content_fields=[SemanticField(field_name="content")],
        ),
    )

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="myHnsw",
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters=HnswParameters(
                    m=4,
                    ef_construction=400,
                    ef_search=500,
                    metric=VectorSearchAlgorithmMetric.COSINE,
                ),
            ),
            ExhaustiveKnnAlgorithmConfiguration(
                name="myExhaustiveKnn",
                kind=VectorSearchAlgorithmKind.EXHAUSTIVE_KNN,
                parameters=ExhaustiveKnnParameters(
                    metric=VectorSearchAlgorithmMetric.COSINE
                ),
            ),
        ],
        profiles=[
            VectorSearchProfile(
                name="myHnswProfile",
                algorithm_configuration_name="myHnsw",
            ),
            VectorSearchProfile(
                name="myExhaustiveKnnProfile",
                algorithm_configuration_name="myExhaustiveKnn",
            ),
        ],
    )

    semantic_search = SemanticSearch(configurations=[semantic_config])

    index = SearchIndex(
        name=name,
        fields=fields,
        semantic_search=semantic_search,
        vector_search=vector_search,
    )

    return index

def gen_documents(path: str) -> List[Dict[str, any]]:
    aoai_api_version = azure_config.aoai_api_version
    openai_service_endoint = azure_config.aoai_endpoint
    openai_deployment = "text-embedding-ada-002"

    token_provider = get_bearer_token_provider(azure_config.credential, "https://cognitiveservices.azure.com/.default")
    client = AzureOpenAI(
        api_version=aoai_api_version,
        azure_endpoint=openai_service_endoint,
        azure_deployment=openai_deployment,
        azure_ad_token_provider=token_provider
    )

    documents = pd.read_csv(path)
    items = []
    for document in documents.to_dict("records"):
        content = document["content"]
        id = str(document["id"])
        title = document["name"]
        url = document["url"]
        emb = client.embeddings.create(input=content, model=openai_deployment)
        rec = {
            "id": id,
            "content": content,
            "filepath": f"{title.lower().replace(' ', '-')}",
            "title": title,
            "url": url,
            "contentVector": emb.data[0].embedding,
        }
        items.append(rec)

    return items

if __name__ == "__main__":
    rag_search = azure_config.search_endpoint
    index_name = "rag-index"

    search_index_client = SearchIndexClient(
        rag_search, azure_config.credential
    )

    delete_index(search_index_client, index_name)
    index = create_index_definition(index_name)
    print(f"creating index {index_name}")
    search_index_client.create_or_update_index(index)
    print(f"index {index_name} created")

    print(f"indexing documents")
    docs = gen_documents("data/sample-documents.csv")
    search_client = SearchClient(
        endpoint=rag_search,
        index_name=index_name,
        credential=azure_config.credential,
    )
    print(f"uploading {len(docs)} documents to index {index_name}")
    ds = search_client.upload_documents(docs)
from dotenv import load_dotenv
load_dotenv()

import os
import pathlib
from ai_search import retrieve_documentation
from promptflow.tools.common import init_azure_openai_client
from promptflow.connections import AzureOpenAIConnection
from promptflow.core import (AzureOpenAIModelConfiguration, Prompty, tool)
from azure_config import AzureConfig 

# Initialize AzureConfig
azure_config = AzureConfig()

def get_embedding(question: str):
    embedding_model = os.environ["AZURE_OPENAI_EMBEDDING_MODEL"]

    connection = AzureOpenAIConnection(
        azure_deployment=embedding_model,
        api_version=azure_config.aoai_api_version,
        api_base=azure_config.aoai_endpoint
    )
    client = init_azure_openai_client(connection)

    return client.embeddings.create(
        input=question,
        model=embedding_model,
    ).data[0].embedding

def get_context(question, embedding):
    return retrieve_documentation(
        question=question,
        index_name="rag-index",
        embedding=embedding,
        search_endpoint=azure_config.search_endpoint
    )

@tool
def get_response(question, chat_history):
    print("inputs:", question)
    embedding = get_embedding(question)
    context = get_context(question, embedding)
    print("context:", context)
    print("getting result...")

    deployment_name = os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT"]

    configuration = AzureOpenAIModelConfiguration(
        azure_deployment=deployment_name,
        api_version=azure_config.aoai_api_version,
        azure_endpoint=azure_config.aoai_endpoint
    )
    override_model = {
        "configuration": configuration,
        "parameters": {"max_tokens": 512}
    }

    data_path = os.path.join(pathlib.Path(__file__).parent.resolve(), "./chat.prompty")
    prompty_obj = Prompty.load(data_path, model=override_model)

    result = prompty_obj(question=question, documents=context)

    print("result: ", result)

    return {"answer": result, "context": context}

if __name__ == "__main__":
    get_response("How can I access my medical records?", [])
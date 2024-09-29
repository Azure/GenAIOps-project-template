from azure.ai.ml import MLClient
from azure.identity import DefaultAzureCredential
import os

class AzureConfig:
    def __init__(self):
        # Load environment variables
        self.subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
        self.resource_group = os.environ["AZURE_RESOURCE_GROUP"]
        self.workspace_name = os.environ["AZUREAI_PROJECT_NAME"]

        # Initialize MLClient with appropriate credentials
        self.ml_client = MLClient(
            self.get_credentials(),
            self.subscription_id,
            self.resource_group,
            self.workspace_name
        )

        # Retrieve Azure OpenAI and Azure AI Search connections and credentials
        self.aoai_connection = self.ml_client.connections.get('aoai-connection')
        self.search_connection = self.ml_client.connections.get('rag-search')

        # Extract necessary details for Azure OpenAI
        self.aoai_endpoint = self.aoai_connection.target
        self.aoai_api_version = self.aoai_connection.metadata.get('ApiVersion', '')
        self.credential = self.get_credentials()

        # Extract necessary details for Azure AI Search
        self.search_endpoint = self.search_connection.target

    def get_credentials(self):
        """
        Determines the appropriate Azure credentials based on the environment.

        Returns:
            Azure credentials object.
        """
        try:
            return DefaultAzureCredential()
        except Exception as e:
            print(f"Error determining credentials: {e}")
            raise
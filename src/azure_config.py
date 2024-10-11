import os
import re

from dotenv import load_dotenv
load_dotenv()

class AzureConfig:
    def __init__(self):
        # Load environment variables for Azure configuration
        self.subscription_id = os.environ["AZURE_SUBSCRIPTION_ID"]
        self.resource_group = os.environ["AZURE_RESOURCE_GROUP"]
        self.workspace_name = os.environ["AZUREAI_PROJECT_NAME"]
        self.location = os.getenv("AZURE_LOCATION", "")
        self.aoai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        self.aoai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "")
        self.search_endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "")
        self.aoai_api_key = "use_managed_identity"
        self.aoai_account_name = self.get_domain_prefix(self.aoai_endpoint)
        self.search_account_name = self.get_domain_prefix(self.search_endpoint)

        if not self.aoai_endpoint:
            # Try to get the connection information from AI Project
            # Initialize MLClient with the loaded credentials and configuration
            from azure.ai.ml import MLClient
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

            # Initialize MLClient with the loaded credentials and configuration
            self.ml_client = MLClient(
                DefaultAzureCredential(),
                self.subscription_id,
                self.resource_group,
                self.workspace_name
            )

            # Retrieve the workspace details from Azure ML
            self.workspace = self.ml_client.workspaces.get(
                name=self.workspace_name,
                resource_group_name=self.resource_group
            )
            self.location = self.workspace.location

            # Retrieve connections for Azure OpenAI and Azure AI Search
            self.aoai_connection = self.ml_client.connections.get('aoai-connection')
            self.search_connection = self.ml_client.connections.get('rag-search')

            # Extract endpoint and API version for Azure OpenAI
            self.aoai_endpoint = self.aoai_connection.target
            self.aoai_api_version = self.aoai_connection.metadata.get('ApiVersion', '')

            # Obtain credentials and API key for Azure OpenAI
            hostname = self.aoai_endpoint.split("://")[1].split("/")[0]
            account_name = hostname.split('.')[0]
            self.cognitive_client = CognitiveServicesManagementClient(DefaultAzureCredential(), self.subscription_id)
            keys = self.cognitive_client.accounts.list_keys(self.resource_group, account_name)
            self.aoai_api_key = keys.key1
            
            # Extract endpoint for Azure AI Search
            self.search_endpoint = self.search_connection.target

            self.aoai_account_name = self.get_domain_prefix(self.aoai_endpoint)
            self.search_account_name = self.get_domain_prefix(self.search_endpoint)

    def get_domain_prefix(self, url):
        match = re.search(r'https?://([^.]+)', url)
        if match:
            return match.group(1)
        return None
import os
import re

from dotenv import load_dotenv
load_dotenv()

class AzureConfig:
    """
    A class to configure and initialize Azure service connections, including Azure ML, 
    Azure OpenAI, and Azure Cognitive Services. This class loads essential environment 
    variables and initializes Azure clients for further operations.

    Methods:
        __init__: Initializes the class with environment variables and Azure clients.

    __init__:
        Initializes the AzureConfig object by loading environment variables and setting 
        up Azure service clients, including MLClient and CognitiveServicesManagementClient.
        
        - Environment Variables:
            - AZURE_SUBSCRIPTION_ID: The Azure subscription ID to use.
            - AZURE_RESOURCE_GROUP: The resource group name containing the Azure services.
            - AZUREAI_PROJECT_NAME: The name of the Azure Machine Learning project.

        - Other Configuration Parameters:
            - AZURE_LOCATION: (Optional) The location of the resources.
            - AZURE_OPENAI_ENDPOINT: (Optional) The endpoint for Azure OpenAI.
            - AZURE_OPENAI_API_VERSION: (Optional) API version for Azure OpenAI.
            - AZURE_SEARCH_ENDPOINT: (Optional) Endpoint for Azure AI Search.

        - Initialization Logic:
            1. Load essential environment variables for subscription, resource group, and workspace.
            2. If all essential variables are present, initialize the Azure MLClient.
            3. Retrieve workspace information and update location if available.
            4. Obtain connections for Azure OpenAI and Azure AI Search via MLClient.
            5. Extract Azure OpenAI API key and endpoint via CognitiveServicesManagementClient.
            6. Extract endpoint names for Azure OpenAI and AI Search.
    """

    def __init__(self):
        """
        Initializes the AzureConfig object by loading environment variables and setting up
        the necessary Azure clients, including MLClient and CognitiveServicesManagementClient.
        """
        # Load essential environment variables, ensuring necessary configurations are set
        self.subscription_id = self.get_env_var("AZURE_SUBSCRIPTION_ID")
        self.resource_group = self.get_env_var("AZURE_RESOURCE_GROUP")
        self.workspace_name = self.get_env_var("AZUREAI_PROJECT_NAME")
        self.check_missing_vars()

        # If essential variables are provided, initialize Azure clients
        if self.subscription_id and self.resource_group and self.workspace_name:
            # Import necessary Azure libraries only when needed to avoid unnecessary dependencies
            from azure.ai.ml import MLClient
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.cognitiveservices import CognitiveServicesManagementClient

            # Initialize the MLClient using DefaultAzureCredential and configuration
            self.ml_client = MLClient(
                DefaultAzureCredential(),
                self.subscription_id,
                self.resource_group,
                self.workspace_name
            )

            # Retrieve workspace details and update location if available
            self.workspace = self.ml_client.workspaces.get(
                name=self.workspace_name,
                resource_group_name=self.resource_group
            )
            self.location = self.workspace.location  # Use workspace location if available

            # Retrieve service connections for Azure OpenAI and AI Search
            self.aoai_connection = self.ml_client.connections.get('aoai-connection')
            self.search_connection = self.ml_client.connections.get('rag-search')

            # Extract Azure OpenAI endpoint and API version from the connection metadata
            self.aoai_endpoint = self.aoai_connection.target
            self.aoai_api_version = self.aoai_connection.metadata.get('ApiVersion', '')

            # Extract the account name from the OpenAI endpoint for Cognitive Services API keys
            hostname = self.aoai_endpoint.split("://")[1].split("/")[0]
            account_name = hostname.split('.')[0]

            # Initialize the CognitiveServicesManagementClient to retrieve API keys
            self.cognitive_client = CognitiveServicesManagementClient(
                DefaultAzureCredential(), self.subscription_id
            )
            keys = self.cognitive_client.accounts.list_keys(self.resource_group, account_name)
            self.aoai_api_key = keys.key1  # Use the first key for authentication

            # Extract the Azure AI Search endpoint from the search connection
            self.search_endpoint = self.search_connection.target

            # Extract domain prefixes for OpenAI and Search services for easier identification
            self.aoai_account_name = self.get_domain_prefix(self.aoai_endpoint)
            self.search_account_name = self.get_domain_prefix(self.search_endpoint)

    def get_env_var(self, var_name):
        """Retrieve environment variable and log if it's not set."""
        value = os.getenv(var_name)
        if value is None:
            print(f"Environment variable '{var_name}' is not set.")
        return value
    
    def check_missing_vars(self):
        """Checks if essential environment variables are missing and exits if necessary."""
        missing_vars = [
            var for var in [
                "AZURE_SUBSCRIPTION_ID", 
                "AZURE_RESOURCE_GROUP", 
                "AZUREAI_PROJECT_NAME"
            ] if not os.getenv(var)
        ]
        if missing_vars:
            print(
                f"Error: The following environment variables are required but not set: "
                f"{', '.join(missing_vars)}", 
            )
            exit(1) 

    def get_domain_prefix(self, url):
        match = re.search(r'https?://([^.]+)', url)
        if match:
            return match.group(1)
        return None
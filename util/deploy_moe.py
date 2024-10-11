import os, uuid
# set environment variables before importing any other code
from dotenv import load_dotenv
load_dotenv()

from azure.ai.ml import MLClient
from azure.ai.ml.entities import ManagedOnlineEndpoint, ManagedOnlineDeployment, Model, Environment, BuildContext
from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.authorization.models import RoleAssignmentCreateParameters
from azure.core.exceptions import ResourceExistsError

from uuid import uuid4
from azure_config import AzureConfig

# Read configuration
azure_config = AzureConfig()

print("Initializing MLClient...")
client = MLClient(
    DefaultAzureCredential(),
    azure_config.subscription_id,
    azure_config.resource_group,
    azure_config.workspace_name
)


def get_ai_studio_url_for_deploy(
    client: MLClient, endpoint_name: str, deployment_name
    ) -> str:
    studio_base_url = "https://ai.azure.com"
    deployment_url = f"{studio_base_url}/projectdeployments/realtime/{endpoint_name}/{deployment_name}/detail?wsid=/subscriptions/{client.subscription_id}/resourceGroups/{client.resource_group_name}/providers/Microsoft.MachineLearningServices/workspaces/{client.workspace_name}&deploymentName={deployment_name}"
    return deployment_url

def output_deployment_details(client, endpoint_name, deployment_name) -> str:
    print("\n ~~~Deployment details~~~")
    print(f"Your online endpoint name is: {endpoint_name}")
    print(f"Your deployment name is: {deployment_name}")
    
    print("\n ~~~Test in the Azure AI Studio~~~")
    print("\n Follow this link to your deployment in the Azure AI Studio:")
    print(get_ai_studio_url_for_deploy(client=client, endpoint_name=endpoint_name, deployment_name=deployment_name))

def deploy_flow(endpoint_name, deployment_name):

    # check if endpoint exists, create endpoint object if not
    try:
        endpoint = client.online_endpoints.get(endpoint_name)
    
    except Exception as e:
        endpoint = ManagedOnlineEndpoint(
            name=endpoint_name,
            properties={
              "enforce_access_to_default_secret_stores": "enabled" # if you want secret injection support
            },
            auth_mode="aad_token" # using aad auth instead of key-based auth
        )

    # Get the directory of the current script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Script directory: {script_dir}")

    # Define the path to the directory, appending the script directory to the relative path
    flow_path = os.path.abspath(os.path.join(script_dir, "../dist"))
    print(f"Flow path: {flow_path}")

    # Create dummy file in connections folder (promptflow issue #1274)
    connections_path = os.path.join(flow_path, "connections")
    os.makedirs(connections_path, exist_ok=True)
    dummy_file_path = os.path.join(connections_path, "dummy.txt")
    with open(dummy_file_path, 'w') as dummy_file:
        pass

    deployment = ManagedOnlineDeployment(
        name=deployment_name,
        endpoint_name=endpoint_name,
        model=Model(
            name="ragflow",
            path=flow_path,  # path to promptflow folder
            properties=[ # this enables the chat interface in the endpoint test tab
                ["azureml.promptflow.source_flow_id", "ragflow"],
                ["azureml.promptflow.mode", "chat"],
                ["azureml.promptflow.chat_input", "question"],
                ["azureml.promptflow.chat_output", "answer"]
            ]
        ),
        environment=Environment(
            build=BuildContext(
                path=flow_path,
            ),
            inference_config={
                "liveness_route": {
                    "path": "/health",
                    "port": 8080,
                },
                "readiness_route": {
                    "path": "/health",
                    "port": 8080,
                },
                "scoring_route":{
                    "path": "/score",
                    "port": 8080,
                },
            },
        ),
        # instance type comes with associated cost.
        # make sure you have quota for the specified instance type
        # See more details here: https://learn.microsoft.com/azure/machine-learning/reference-managed-online-endpoints-vm-sku-list
        instance_type="Standard_DS3_v2",
        instance_count=1,
        environment_variables={
            "PRT_CONFIG_OVERRIDE": f"deployment.subscription_id={client.subscription_id},deployment.resource_group={client.resource_group_name},deployment.workspace_name={client.workspace_name},deployment.endpoint_name={endpoint_name},deployment.deployment_name={deployment_name}",
            "AZURE_SUBSCRIPTION_ID": os.environ["AZURE_SUBSCRIPTION_ID"],
            "AZURE_RESOURCE_GROUP": os.environ["AZURE_RESOURCE_GROUP"],
            "AZUREAI_PROJECT_NAME": os.environ["AZUREAI_PROJECT_NAME"],
            "AZURE_OPENAI_ENDPOINT": azure_config.aoai_endpoint,
            "AZURE_OPENAI_API_VERSION": azure_config.aoai_api_version,
            "AZURE_SEARCH_ENDPOINT": azure_config.search_endpoint,
            "AZURE_OPENAI_CHAT_DEPLOYMENT": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT"),
            "AZURE_OPENAI_EMBEDDING_MODEL": os.getenv("AZURE_OPENAI_EMBEDDING_MODEL"),
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": os.getenv("AZURE_OPENAI_EMBEDDING_MODEL")  # using the same name for the deployment as the model for simplicity
        }
    )

    # 1. create endpoint
    endpoint = client.begin_create_or_update(endpoint).result() # result() means we wait on this to complete

    # 2. provide endpoint access to Azure Open AI resource
    create_role_assignment(
        scope=f"/subscriptions/{client.subscription_id}/resourceGroups/{azure_config.resource_group}/providers/Microsoft.CognitiveServices/accounts/{azure_config.aoai_account_name}",
        role_name="Cognitive Services OpenAI User",
        principal_id=endpoint.identity.principal_id
        )
    
    create_role_assignment(
        scope=f"/subscriptions/{client.subscription_id}/resourceGroups/{azure_config.resource_group}/providers/Microsoft.CognitiveServices/accounts/{azure_config.aoai_account_name}",
        role_name="Cognitive Services Contributor",
        principal_id=endpoint.identity.principal_id
        )

    create_role_assignment(
            scope=f"/subscriptions/{client.subscription_id}/resourceGroups/{azure_config.resource_group}",
            role_name="Contributor",
            principal_id=endpoint.identity.principal_id
        )


    # 3. provide endpoint access to Azure AI Search resource
    create_role_assignment(
        scope=f"/subscriptions/{client.subscription_id}/resourceGroups/{azure_config.resource_group}/providers/Microsoft.Search/searchServices/{azure_config.search_account_name}",
        role_name="Search Index Data Contributor",
        principal_id=endpoint.identity.principal_id
        )
    
    # 4. provide endpoint access to workspace
    create_role_assignment(
        scope=f"/subscriptions/{azure_config.subscription_id}/resourceGroups/{azure_config.resource_group}/providers/Microsoft.MachineLearningServices/workspaces/{azure_config.workspace_name}",
        role_name="Contributor",
        principal_id=endpoint.identity.principal_id
        )

    # 5. create deployment
    deployment = client.begin_create_or_update(deployment).result()

    # 6. update endpoint traffic for the deployment
    endpoint.traffic = {deployment_name: 100} # 100% of traffic
    endpoint = client.begin_create_or_update(endpoint).result()

    output_deployment_details(
        client=client,
        endpoint_name=endpoint_name,
        deployment_name=deployment_name
        )

def create_role_assignment(scope, role_name, principal_id):
    
    try:

        # Get credential
        credential = DefaultAzureCredential()

        # Instantiate the authorization management client
        auth_client = AuthorizationManagementClient(
            credential=credential,
            subscription_id=client.subscription_id
            )
        
        roles = list(auth_client.role_definitions.list(
            scope,
            filter="roleName eq '{}'".format(role_name)))
        
        assert len(roles) == 1
        role = roles[0]
        
        # Create role assignment properties
        parameters = RoleAssignmentCreateParameters(
            role_definition_id=role.id,
            principal_id=principal_id,
            principal_type="ServicePrincipal"
            )
    
        # Create role assignment
        role_assignment = auth_client.role_assignments.create(
            scope=scope,
            role_assignment_name=str(uuid4()),
            parameters=parameters
        )
    except ResourceExistsError:
        print("Role assignment already exists.")
    except Exception as e:
        print(f"An error occurred during role assignment: {e}")




if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint-name", help="endpoint name to use when deploying or invoking the flow", type=str)
    parser.add_argument("--deployment-name", help="deployment name used to deploy to a managed online endpoint in AI Studio", type=str)
    args = parser.parse_args()

    endpoint_name = args.endpoint_name if args.endpoint_name else f"rag-0000-endpoint"
    deployment_name = args.deployment_name if args.deployment_name else f"rag-0000-deployment"

    deploy_flow(endpoint_name, deployment_name)



    
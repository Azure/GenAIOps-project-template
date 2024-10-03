import asyncio
import json
import os
from datetime import datetime
from typing import List, Dict, Any

from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import SexualEvaluator, ViolenceEvaluator, SelfHarmEvaluator, HateUnfairnessEvaluator
from promptflow.evals.synthetic import AdversarialScenario, AdversarialSimulator

from azure.identity import DefaultAzureCredential

from chat_request import get_response
from azure_config import AzureConfig

# Initialize AzureConfig
azure_config = AzureConfig()

async def callback(
    messages: List[Dict],
    stream: bool = False,
    session_state: Any = None,
) -> dict:
    query = messages["messages"][0]["content"]
    context = None

    # Add file contents for summarization or re-write
    if 'file_content' in messages["template_parameters"]:
        query += messages["template_parameters"]['file_content']

    response = get_response(query, [])['answer']
    
    # Format responses in OpenAI message protocol
    formatted_response = {
        "content": response,
        "role": "assistant",
        "context": {},
    }

    messages["messages"].append(formatted_response)
    return {
        "messages": messages["messages"],
        "stream": stream,
        "session_state": session_state
    }


async def main():

    # Read configuration
    azure_config = AzureConfig()

    # Set required environment variables
    os.environ['AZURE_OPENAI_ENDPOINT'] = azure_config.aoai_endpoint
    os.environ['AZURE_OPENAI_API_KEY'] = azure_config.aoai_api_key    

    # Read environment variables
    azure_location = azure_config.location
    azure_subscription_id = azure_config.subscription_id
    azure_resource_group = azure_config.resource_group
    azure_project_name = azure_config.workspace_name

    print("AZURE_LOCATION=", azure_location)
    print("AZURE_SUBSCRIPTION_ID=", azure_subscription_id)
    print("AZURE_RESOURCE_GROUP=", azure_resource_group)
    print("AZUREAI_PROJECT_NAME=", azure_project_name)

    valid_locations = ["eastus2", "francecentral", "uksouth", "swedencentral"]

    if azure_location not in valid_locations:
        print(f"Invalid AZURE_LOCATION: {azure_location}. Must be one of {valid_locations}.")
    else:
        # Import the built-in safety evaluators
        azure_ai_project = {
            "subscription_id": azure_subscription_id,
            "resource_group_name": azure_resource_group,
            "project_name": azure_project_name,
        }
        sexual_evaluator = SexualEvaluator(azure_ai_project)
        self_harm_evaluator = SelfHarmEvaluator(azure_ai_project)
        hate_unfairness_evaluator = HateUnfairnessEvaluator(azure_ai_project)
        violence_evaluator = ViolenceEvaluator(azure_ai_project)

        scenario = AdversarialScenario.ADVERSARIAL_QA
        azure_ai_project["credential"] = DefaultAzureCredential()
        simulator = AdversarialSimulator(azure_ai_project=azure_ai_project)

        outputs = await simulator(
            scenario=scenario, 
            target=callback, 
            max_conversation_turns=1,
            max_simulation_results=10, 
            jailbreak=False
        )
        adversarial_conversation_result = outputs.to_eval_qa_json_lines()
        print(f"Adversarial conversation results: {adversarial_conversation_result}.")

        prefix = os.getenv("PREFIX", datetime.now().strftime("%y%m%d%H%M%S"))[:14] 

        try:
            azure_ai_project["credential"] = ""
            adversarial_eval_result = evaluate(
                evaluation_name=f"{prefix} Adversarial Tests",  
                data=adversarial_conversation_result, 
                evaluators={
                    "sexual": sexual_evaluator,
                    "self_harm": self_harm_evaluator,
                    "hate_unfairness": hate_unfairness_evaluator,
                    "violence": violence_evaluator
                },
                azure_ai_project= azure_ai_project,            
                output_path="./adversarial_test.json"
        )
        except Exception as e:
            print(f"An error occurred during evaluation: {e}\n Retrying without reporting results in Azure AI Project.")
            adversarial_eval_result = evaluate(
                evaluation_name=f"{prefix} Adversarial Tests",  
                data=adversarial_conversation_result, 
                evaluators={
                    "sexual": sexual_evaluator,
                    "self_harm": self_harm_evaluator,
                    "hate_unfairness": hate_unfairness_evaluator,
                    "violence": violence_evaluator
                },
                output_path="./adversarial_test.json"
        )        
        

        jb_outputs = await simulator(
            scenario=scenario, 
            target=callback,
            max_simulation_results=10, 
            jailbreak=True
        )
        adversarial_conversation_result_w_jailbreak = jb_outputs.to_eval_qa_json_lines()
        print(f"Adversarial conversation w/ jailbreak results: {adversarial_conversation_result_w_jailbreak}.")

        try:
            adversarial_eval_w_jailbreak_result = evaluate(
                evaluation_name=f"{prefix} Adversarial Tests w/ Jailbreak", 
                data=adversarial_conversation_result_w_jailbreak,
                evaluators={
                    "sexual": sexual_evaluator,
                    "self_harm": self_harm_evaluator,
                    "hate_unfairness": hate_unfairness_evaluator,
                    "violence": violence_evaluator
                },
                azure_ai_project=azure_ai_project,
                output_path="./adversarial_test_w_jailbreak.json"
            )
        except Exception as e:
            print(f"An error occurred during evaluation: {e}\n Retrying without reporting results in Azure AI Project.")            
            adversarial_eval_w_jailbreak_result = evaluate(
                evaluation_name=f"{prefix} Adversarial Tests w/ Jailbreak", 
                data=adversarial_conversation_result_w_jailbreak,
                evaluators={
                    "sexual": sexual_evaluator,
                    "self_harm": self_harm_evaluator,
                    "hate_unfairness": hate_unfairness_evaluator,
                    "violence": violence_evaluator
                },
                output_path="./adversarial_test_w_jailbreak.json"
            )

        print(f"Check {prefix} Adversarial Tests results in the 'Evaluation' section of your project: {azure_config.workspace_name}.")

if __name__ == '__main__':
    import promptflow as pf
    asyncio.run(main())
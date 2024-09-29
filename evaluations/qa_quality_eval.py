import os
import json
from datetime import datetime

from promptflow.client import PFClient
from promptflow.core import AzureOpenAIModelConfiguration
from promptflow.evals.evaluate import evaluate
from promptflow.evals.evaluators import RelevanceEvaluator, FluencyEvaluator, GroundednessEvaluator, CoherenceEvaluator

def main():

    # Read environment variables
    azure_location = os.getenv("AZURE_LOCATION")
    azure_subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
    azure_resource_group = os.getenv("AZURE_RESOURCE_GROUP")
    azure_project_name = os.getenv("AZUREAI_PROJECT_NAME")
    prefix = os.getenv("PREFIX", datetime.now().strftime("%y%m%d%H%M%S"))[:14] 

    print("AZURE_LOCATION =", azure_location)
    print("AZURE_SUBSCRIPTION_ID =", azure_subscription_id)
    print("AZURE_RESOURCE_GROUP =", azure_resource_group)
    print("AZUREAI_PROJECT_NAME=", azure_project_name)
    print("PREFIX =", prefix)    

    ##################################
    ## Base Run
    ##################################

    pf = PFClient()
    flow = "./src"  # path to the flow
    data = "./evaluations/test-dataset.jsonl"  # path to the data file

    # base run
    base_run = pf.run(
        flow=flow,
        data=data,
        column_mapping={
            "question": "${data.question}",
            "chat_history": []
        },
        stream=True,
    )
    
    responses = pf.get_details(base_run)
    print(responses.head(10))

    # Convert to jsonl
    relevant_columns = responses[['inputs.question', 'inputs.chat_history', 'outputs.answer', 'outputs.context']]
    relevant_columns.columns = ['question', 'chat_history', 'answer', 'context']
    data_list = relevant_columns.to_dict(orient='records')
    with open('responses.jsonl', 'w') as f:
        for item in data_list:
            f.write(json.dumps(item) + '\n')    

    ##################################
    ## Evaluation
    ##################################

    # Initialize Azure OpenAI Connection with your environment variables
    model_config = AzureOpenAIModelConfiguration(
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        azure_deployment=os.environ.get("AZURE_OPENAI_DEPLOYMENT"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION"),
    )
    
    azure_ai_project = {
        "subscription_id": os.getenv("AZURE_SUBSCRIPTION_ID"),
        "resource_group_name": os.getenv("AZURE_RESOURCE_GROUP"),
        "project_name": os.getenv("AZUREAI_PROJECT_NAME"),
    }    

    # https://learn.microsoft.com/en-us/azure/ai-studio/how-to/develop/flow-evaluate-sdk
    fluency_evaluator = FluencyEvaluator(model_config=model_config)
    groundedness_evaluator = GroundednessEvaluator(model_config=model_config)
    relevance_evaluator = RelevanceEvaluator(model_config=model_config)
    coherence_evaluator = CoherenceEvaluator(model_config=model_config)

    data = "./responses.jsonl"  # path to the data file

    try:
        result = evaluate(
            evaluation_name=f"{prefix} Quality Evaluation",
            data=data,
            evaluators={
                "Fluency": fluency_evaluator,
                "Groundedness": groundedness_evaluator,
                "Relevance": relevance_evaluator,
                "Coherence": coherence_evaluator
            },
            azure_ai_project=azure_ai_project,
            output_path="./qa_flow_quality_eval.json"
        )
    except Exception as e:
        print(f"An error occurred during evaluation: {e}\n Retrying without reporting results in Azure AI Project.")
        result = evaluate(
            evaluation_name=f"{prefix} Quality Evaluation",
            data=data,
            evaluators={
                "Fluency": fluency_evaluator,
                "Groundedness": groundedness_evaluator,
                "Relevance": relevance_evaluator,
                "Coherence": coherence_evaluator
            },
            output_path="./qa_flow_quality_eval.json"
        )        

if __name__ == '__main__':
    import promptflow as pf
    main()
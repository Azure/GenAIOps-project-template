from promptflow.client import PFClient
from promptflow.core import AzureOpenAIModelConfiguration
from azure_config import AzureConfig 
import os

def main():

    pf = PFClient()

    # Set the required environment variables
    azure_config = AzureConfig()
    os.environ['AZURE_OPENAI_ENDPOINT'] = azure_config.aoai_endpoint
    os.environ['AZURE_OPENAI_API_KEY'] = azure_config.aoai_api_key    

    flow = "./src/chat.prompty"  # path to the prompty file
    data = "./evaluations/test-dataset.jsonl"  # path to the data file

    # base run
    base_run = pf.run(
        flow=flow,
        data=data,
        column_mapping={
            "question": "${data.question}",
            "documents": "${data.documents}"
        },
        stream=True,
    )
    details = pf.get_details(base_run)
    print(details.head(10))


    # Evaluation run
    eval_prompty = "./evaluations/prompty-answer-score-eval.prompty"
    eval_run = pf.run(
        flow=eval_prompty,
        data=data,  
        run=base_run, 
        column_mapping={
            "question": "${data.question}",
            "answer": "${run.outputs.output}",
            "ground_truth": "${data.ground_truth}",
        },
        stream=True,
    )

    details = pf.get_details(eval_run)

    print(details.head(10))

    details = pf.get_details(eval_run)
    details.to_excel("prompty-answer-score-eval.xlsx", index=False)


if __name__ == '__main__':
    import promptflow as pf
    main()
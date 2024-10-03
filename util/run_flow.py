import os
import json
import argparse
from datetime import datetime
import promptflow as pf

from promptflow.client import PFClient
from promptflow.core import AzureOpenAIModelConfiguration

from azure_config import AzureConfig

def main(question):

    # Read configuration
    azure_config = AzureConfig()

    # Set required environment variables
    os.environ['AZURE_OPENAI_ENDPOINT'] = azure_config.aoai_endpoint
    os.environ['AZURE_OPENAI_API_KEY'] = azure_config.aoai_api_key    

    ##################################
    ## Base Run
    ##################################

    pf_client = PFClient()
    flow = "./src"  # path to the flow
    data = "./temp-dataset.jsonl"  # path to the data file

    # Create data file and add the JSON content to it
    with open(data, 'w') as f:
        json_line = json.dumps({"question": question, "chat_history": "[]"})
        f.write(json_line + '\n')  # Write the JSON line followed by a newline

    # Base run
    base_run = pf_client.run(
        flow=flow,
        data=data,
        column_mapping={
            "question": "${data.question}",
            "chat_history": []
        },        
        stream=True,
    )

    responses = pf_client.get_details(base_run)
    answer = responses.loc[0, 'outputs.answer']
    print(answer)
    
    # Delete data file if it exists
    if os.path.exists(data):
        os.remove(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Run PromptFlow with a specific question.')
    parser.add_argument('question', type=str, nargs='?', default='Are telehealth services covered by insurance at Lamna Healthcare?', help='The question to be processed by PromptFlow')
    args = parser.parse_args()
    main(args.question)
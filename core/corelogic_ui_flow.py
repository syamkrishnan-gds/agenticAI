### This file contains the multi-agent workflow for the CoreLogic API flow. The workflow consists of 5 agents - Test Manager, Utterances Generator, Utterances Reviewer, Chatbot Tester and ADO Helper.

### Author: Arun Sivaraj A P

from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import  TextMentionTermination, MaxMessageTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_core.tools import FunctionTool
from autogen_agentchat.ui import Console
import urllib.request, requests
import json
import os
import ssl
from base64 import b64encode

from config.config import CBTA_API_KEY,Model_Name,Api_Version,Azure_Endpoint,chatbot_endpoint, chatbot_api_key, ado_org, ado_project, ado_pat_token
from utils.tasks import TEST_MANAGER_TASK, UTTERANCES_GENERATOR_TASK, UTTERANCES_REVIEWER_TASK, CHATBOT_TESTER_TASK, ADO_HELPER_TASK

# Create the token provider
token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# Allow self-signed certificates
def allowSelfSignedHttps(allowed):
    # bypass the server certificate verification on client side
    if allowed and not os.environ.get('PYTHONHTTPSVERIFY', '') and getattr(ssl, '_create_unverified_context', None):
        ssl._create_default_https_context = ssl._create_unverified_context

allowSelfSignedHttps(True)


# Calling the function to get the chatbot response
def get_chatbot_response(utterance: str) -> str:

    data = {'chat_input': utterance}
    body = str.encode(json.dumps(data))

    # Chatbot API and KEY
    url = chatbot_endpoint
    api_key = chatbot_api_key

    if not api_key:
        raise Exception("A key should be provided to invoke the endpoint")

    headers = {'Content-Type': 'application/json', 'Authorization': ('Bearer ' + api_key)}

    req = urllib.request.Request(url, body, headers)

    try:

        response = urllib.request.urlopen(req)
        result = response.read()
        result_json = json.loads(result.decode('utf-8'))
        answer = result_json.get('chat_output', 'An error occurred. Please contact Arun Sivaraj A P.')
        return answer
    
    except urllib.error.HTTPError as error:
        return f"The request failed with status code: {error.code}, message: {error.reason}"

# Calling the function to create an issue in Azure DevOps board
def create_ado_issue(testcase_num: str, issue_details: str) -> str:
    # Azure DevOps Details
    ADO_ORG = ado_org
    ADO_PROJECT = ado_project
    ADO_PAT = ado_pat_token

    # Base64 encode the PAT for authentication
    encoded_pat = b64encode(f":{ADO_PAT}".encode()).decode()

    # API Endpoint to Create an Issue
    ADO_API_URL = f"https://dev.azure.com/{ADO_ORG}/{ADO_PROJECT}/_apis/wit/workitems/$Issue?api-version=7.1-preview.3"

    # Headers for Authentication and Content
    headers = {
        "Content-Type": "application/json-patch+json",
        "Authorization": f"Basic {encoded_pat}"
    }

    payload = [
        {"op": "add", "path": "/fields/System.Title", "value": f"Defect for Testcase Id : {testcase_num}"},
        {"op": "add", "path": "/fields/System.Description", "value": f"Issue Details: {issue_details}"},
        {"op": "add", "path": "/fields/System.Tags", "value": "QEiAgent"},
        {"op": "add", "path": "/fields/System.AssignedTo", "value": "Arun Sivaraj A P"}
    ]

    response = requests.post(ADO_API_URL, headers=headers, json=payload)

    if response.status_code == 200 or response.status_code == 201:
        return(f"Defect created successfully for Testcase ID: {testcase_num}")
    else:
        return(f"An error occurred while raising defect for Testcase ID: {testcase_num}")

# Creating Termination Conditions
def call_termination_conditions() -> str:
    text_mention = TextMentionTermination("TASK COMPLETED")
    max_messages = MaxMessageTermination(max_messages=10)
    return text_mention | max_messages

# Multi-Agent Workflow function
async def start_workflow(user_query):

    # |Agent               | Temperature | Top_k | Top_p | Rationale                       |
    # |--------------------|-------------|-------|-------|---------------------------------|
    # |Test Manager        | 0.2         | 40    | 0.7   | Coordination & Task Execution   |
    tm_model_client = AzureOpenAIChatCompletionClient(
        azure_deployment=Model_Name,
        model=Model_Name,
        api_version=Api_Version,
        azure_endpoint=Azure_Endpoint,
        temperature=0.2,
        top_k=40,
        top_p=0.7,
        api_key=CBTA_API_KEY
    )
   
    Test_Manager_Agent = AssistantAgent(
    "Test_Manager_Agent",
    model_client=tm_model_client,
    system_message=TEST_MANAGER_TASK
    )

    # | Agent              | Temperature | Top_k | Top_p | Rationale                       |
    # |--------------------|-------------|-------|-------|---------------------------------|
    # | Utterance Generator| 0.9         | 100   | 0.95  | Creative utterances             |
    ug_model_client = AzureOpenAIChatCompletionClient(
        azure_deployment=Model_Name,
        model=Model_Name,
        api_version=Api_Version,
        azure_endpoint=Azure_Endpoint,
        temperature=0.9,
        top_p=0.95,
        top_k=100,
        api_key=CBTA_API_KEY
    )

    # Utterances Generator Agent - Generates diverse utterances based on a given intent
    Utterances_Generator_Agent = AssistantAgent(
    "Utterances_Generator_Agent",
    model_client=ug_model_client,
    system_message=UTTERANCES_GENERATOR_TASK,
    )


    # | Agent              | Temperature | Top_k | Top_p | Rationale                       |
    # |--------------------|-------------|-------|-------|---------------------------------|
    # | Utterance Reviewer | 0.5         | 50    | 0.8   | Balanced creativity & precision |
    ur_model_client = AzureOpenAIChatCompletionClient(
        azure_deployment=Model_Name,
        model=Model_Name,
        api_version=Api_Version,
        azure_endpoint=Azure_Endpoint,
        temperature=0.5,
        top_p=0.8,
        top_k=50,
        api_key=CBTA_API_KEY
    )

    # Utterances Reviewer Agent - Reviews generated utterances, assesses their quality and correct it
    Utterances_Reviewer_Agent = AssistantAgent (
    "Utterances_Reviewer_Agent",
    model_client=ur_model_client,
    system_message=UTTERANCES_REVIEWER_TASK,
    )

   
    # Real_Chatbot_Conversation Tool - Calling the function tool to get the chatbot response
    Real_Chatbot_Conversation = FunctionTool(
        get_chatbot_response, 
        description="Calls the get_chatbot_response function with an utterance and returns the response received."
    )

    # | Agent              | Temperature | Top_k | Top_p | Rationale                       |
    # |--------------------|-------------|-------|-------|---------------------------------|
    # | Chatbot Tester     | 0.5         | 50    | 0.8   | Balanced creativity & precision |
    ct_model_client = AzureOpenAIChatCompletionClient(
        azure_deployment=Model_Name,
        model=Model_Name,
        api_version=Api_Version,
        azure_endpoint=Azure_Endpoint,
        temperature=0.5,
        top_p=0.8,
        top_k=50,
        api_key=CBTA_API_KEY
    )
    
    # Chatbot Tester Agent - Tests the chatbot responses by calling the chatbot conversation tool
    Chatbot_Tester_Agent = AssistantAgent(
    "Chatbot_Tester_Agent",
    model_client=ct_model_client,
    tools=[Real_Chatbot_Conversation],
    system_message=CHATBOT_TESTER_TASK,
    )

    
    # ADO helper tool - Calling the function tool to create issue in Azure DevOps
    ADO_helper = FunctionTool(
        create_ado_issue, 
        description="Calls the create_ado_issue function with testcase id & issue details for each partial / failed testcase to create an issue in ADO and returns the response."
    )


    # | Agent              | Temperature | Top_k | Top_p | Rationale                       |
    # |--------------------|-------------|-------|-------|---------------------------------|
    # | ADO Helper         | 0.1         | 20    | 0.5   | Technical precision             |
    ado_model_client = AzureOpenAIChatCompletionClient(
        azure_deployment=Model_Name,
        model=Model_Name,
        api_version=Api_Version,
        azure_endpoint=Azure_Endpoint,
        temperature=0.1,
        top_p=0.5, 
        top_k=20,
        api_key=CBTA_API_KEY
    )

    # ADO Agent - Raise an issue for the failing testcase in ADO by calling the ADO helper Tool 
    ADO_Helper_Agent = AssistantAgent(
    "ADO_Helper_Agent",
    model_client=ado_model_client,
    tools=[ADO_helper],
    system_message=ADO_HELPER_TASK,
    )

    # Termination Conditions
    termination = call_termination_conditions()

    # Form a team with the agents and do the task
    team = SelectorGroupChat(
        [Test_Manager_Agent, Utterances_Generator_Agent, Utterances_Reviewer_Agent, Chatbot_Tester_Agent,ADO_Helper_Agent],
        model_client=tm_model_client,
        termination_condition=termination,
    )

    try:
        await Console(team.run_stream(task=user_query))
    except Exception as e:
        print(f"Error in multi-agent workflow: {str(e)}")
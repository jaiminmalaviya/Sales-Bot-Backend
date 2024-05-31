import os
from db import db
from dotenv import load_dotenv

from langchain_community.vectorstores import PineconeVectorStore as PineconeLC
from langchain_openai import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from datetime import datetime, timezone


load_dotenv()
Account = db[os.getenv("ACCOUNT_COLLECTION_NAME")]

def add_industry(company_name):
    embeddings = OpenAIEmbeddings()
    vectorstore = PineconeLC.from_existing_index("sales-bot", embeddings)
    filters = {
        "client":{ "$eq" : company_name}
    }
    retriever = vectorstore.as_retriever(search_type='similarity',
                                            search_kwargs={
                                                'k': 5,
                                                'filter': filters if filters is not None else {}
                                            }, )
    # print(retriever)
    prompt = PromptTemplate.from_template("""Given the following information about a company, 
                                          determine the most likely industry it operates in:

                                            Company Name: {company_name}
                                            Context: {context}
                                        
                                          Instructions:
                                            Do not use any additional information beyond the provided context.
                                            Provide a single industry name as the output. 
                                            provide only the industry name based on your reasoning in no more than 3 words and if you have no idea about the industry then return the word unknown.
                            """)

    llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)

    rag_chain = (
            {"context": retriever, "company_name": RunnablePassthrough()}
            | prompt
            | llm
            | StrOutputParser()
    )

    result = rag_chain.invoke(company_name)
    Account.find_one_and_update({'name':company_name},{"$set": {"tags": [result], "updatedAt": datetime.now(timezone.utc)}})
    return result


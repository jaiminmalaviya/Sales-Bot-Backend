from enum import Enum
from flask import jsonify, request
from pymongo import ReturnDocument

from db import db
from dotenv import load_dotenv
import os

from langchain_community.vectorstores import Pinecone as PineconeLC
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough, RunnableParallel
from kafka_setup.kafka_producer import message_producer
from operator import itemgetter
from datetime import datetime, timezone
from bson.objectid import ObjectId
from helpers.helper import parse_json

load_dotenv()

Account = db[os.getenv("ACCOUNT_COLLECTION_NAME")]
Icebreaker = db[os.getenv("ICEBREAKER_COLLECTION_NAME")]
Feedback = db[os.getenv("FEEDBACK_COLLECTION_NAME")]


def handle_query():
    try:
        query = request.json.get("q")
        embeddings = OpenAIEmbeddings()
        docsearch = PineconeLC.from_existing_index("sales-bot", embeddings)
        docs = docsearch.similarity_search(query)

        results = []
        for doc in docs:
            temp = {
                "content": doc.page_content,
                "metadata": doc.metadata
            }
            print(temp)
            results.append(temp)

        return jsonify({"results": results}), 200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500


def handle_question():
    try:
        query = request.json.get("q")
        filters = request.json.get("filters")
        embeddings = OpenAIEmbeddings()
        vectorstore = PineconeLC.from_existing_index("sales-bot", embeddings)

        retriever = vectorstore.as_retriever(search_type='similarity',
                                             search_kwargs={
                                                 'k': 5,
                                                 'filter': filters if filters is not None else {}
                                             }, )

        prompt = PromptTemplate.from_template("""You are an assistant for question-answering tasks. 
                                Use the following pieces of retrieved context to answer the question. 
                                If you don't know the answer, just say that you don't know. 
                                Use three sentences maximum and keep the answer concise unless the question explicitly
                                asks to provide a detailed answer.
                                
                                Question: {question}
                                Context: {context}
                                Answer:""")

        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)

        rag_chain = (
                {"context": retriever, "question": RunnablePassthrough()}
                | prompt
                | llm
                | StrOutputParser()
        )

        result = rag_chain.invoke(query)
        return jsonify({"result": result}), 200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500


def add_industry_controller():
    try:
        company_name = request.json.get('company_name')

        if not company_name:
            return jsonify({"type": "error","message": "Please provide company name!!"}),400
        data = {
            "company_name": company_name
        }
        message_producer(os.getenv("INDUSTRY_CONSUMER"), data)
        return jsonify({"message": "Added industry!!!"}), 200
    except Exception as e:
        return jsonify({"type": "error","message": "Failed to generate industry: {}".format(str(e))}), 500


def icebreaker():
    try:
        company_name = request.json.get('company_name')
        client_name = request.json.get('client_name')
        sales_owner = request.json.get('sales_owner')

        if company_name is None or client_name is None or sales_owner is None:
            return jsonify({"type": "error","message": "fields required: ['company_name', 'client_name', 'sales_owner']"}), 400

        filters = {
            "$or": [
                {
                    "client": {
                        "$in": [company_name, "AlphaBI"]
                    }
                },
                {
                    "contact": client_name
                }
            ]
        }

        embeddings = OpenAIEmbeddings()
        vectorstore = PineconeLC.from_existing_index("sales-bot", embeddings)
        retriever = vectorstore.as_retriever(search_type='similarity',
                                             search_kwargs={
                                                 'k': 10,
                                                 'filter': filters if filters is not None else {}
                                             }, )
        # print(retriever)
        prompt = PromptTemplate.from_template("""
        You are an experienced business developer executive at 'AlphaBI'. Generate an icebreaker message to a client named 
        {client_name} at a company called {company_name}. 
        
        Use the context that you are provided below in such a way that tells the client that how can AlphaBI help them in 
        digital transformation based on the past work that AlphaBI has done with companies that were in similar field as 
        client's or anyhow there'e connection between client and previously worked companies . 
        
        If you fail to find any information, do not try to generate a generic message and instead respond with
        'Generation Failed'. However if you do find relevant information, generate an attractive message addressed to
        the client by name.
        
        Strictly follow the instructions provided to craft the message.
         
         Context: 
         {context}
         
         Instructions:
         - Do not use tha mail format. make it just a simple message for linkedIn.   
         - Try to make the massage as AlphaBI has sent it not the Business Development Analyst
         - Message length should not exceed four sentence. Each sentence should be 15 words at most.
         - Do not use any additional information beyond the provided context
         - Structure the message in AIDA framework format
        """)

        doc_prompt = f"""
            Get information about the company whose name is somewhat similar to or equal to '{company_name}' like 
            what kind of work it does, what industry it works in. Also find out information about the role of 
            {client_name} in the company.Furthermore, also find information about the works done by AlphaBI 
            that are somewhat or very much similar to the type of work {company_name} does.
        """

        llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=1)

        def format_docs(ctx_docs):
            return "\n\n".join(ctx.page_content for ctx in ctx_docs)

        rag_chain_from_docs = (
                RunnablePassthrough.assign(context=(lambda x: format_docs(x["context"])))
                | prompt
                | llm
                | StrOutputParser()
        )

        documents = retriever.get_relevant_documents(doc_prompt)

        rag_chain_with_source = RunnableParallel(
            {
                "context": itemgetter("context"),
                "company_name": itemgetter("company_name"),
                "client_name": itemgetter("client_name"),
            }
        ).assign(answer=rag_chain_from_docs)

        results = rag_chain_with_source.invoke({"context": documents,
                                                "company_name": company_name,
                                                "client_name": client_name})

        docs = results["context"]
        sources = []

        for doc in docs:
            sources.append({
                "content": doc.page_content,
                "metadata": doc.metadata
            })

        results["context"] = sources

        ib = Icebreaker.insert_one({
            "content": results["answer"],
            "account": company_name,
            "contact": client_name,
            "feedbacks": [],
            "context":results["context"],
            "createdAt": datetime.now(timezone.utc),
            "generatedBy": sales_owner
        })

        results["_id"] = str(ib.inserted_id)
        return jsonify(results), 200

    except Exception as e:
        print(e)
        return jsonify({"type": "error","message": "Failed to generate icebreaker: {}".format(str(e))}), 500


def rate_icebreaker():
    try:
        icebreaker_id = request.json.get("icebreaker_id")
        icebreaker_content = request.json.get("icebreaker_content")
        sales_owner = request.json.get("sales_owner")
        sales_owner_id = request.json.get("sales_owner_id")
        value = int(request.json.get("value"))

        if value is None or value not in [-1, 0, 1]:
            return jsonify({"type": "error","message": f"Illegal feedback value: {value}"}), 400

        if icebreaker_id is None or sales_owner is None:
            return jsonify({"type": "error", "message": "Field 'icebreaker_id', 'sales_owner' is required"}), 500

        fb = Feedback.find_one_and_update({
            "icebreaker": ObjectId(icebreaker_id),
            "sales_owner_id": ObjectId(sales_owner_id),
        }, {
            "$set": {
                # "icebreaker": ObjectId(icebreaker_id),
                "content": icebreaker_content,
                "sales_owner": sales_owner,
                "sales_owner_id": ObjectId(sales_owner_id),
                "value": value
            }
        }, upsert=True, return_document=ReturnDocument.AFTER)

        Icebreaker.find_one_and_update({
            "_id": ObjectId(icebreaker_id)
        }, {
            "$addToSet": {
                "feedbacks": fb["_id"]
            }
        })

        return jsonify({"message": "Feedback Received", "data": {"_id": str(fb["_id"])}}), 200

    except Exception as e:
        print(e)
        return jsonify({"type": "error","message": "Failed to generate icebreaker feedback: {}".format(str(e))}), 500


def get_icebreakers():
    try:
        limit = int(request.args.get("limit")) if request.args.get("limit") is not None else 5
        skip = int(request.args.get("skip")) if request.args.get("skip") is not None else 0
        account = request.args.get("account")
        contact = request.args.get("contact")
        sales_owner = request.args.get("sales_owner")

        count = Icebreaker.count_documents({
            "account": account,
            "contact": contact
        })
        
        if account is None:
            return jsonify({"type": "error", "message": "'account' is required"}), 400

        response = Icebreaker.aggregate([
            {
              "$match": {
                  "account": account,
                  "contact": contact  
              }
            },
            {
                "$sort": {"createdAt": -1}
            },
            {
                "$skip": skip
            },
            {
                "$limit": limit
            },
            {
                "$lookup":
                    {
                        "from": "feedback_cl",
                        "localField": "feedbacks",
                        "foreignField": "_id",
                        "let": {"sales_owner": sales_owner},
                        "pipeline": [],
                        "as": "feedbacks",
                    },
            }
        ])
        data = parse_json(response)

        if not data:
            return jsonify({"message": "No icebreakers found"}), 200

        return jsonify({"data": data, "pagination": {"total_count": count, "offset": skip, "limit": limit}}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "Failed to generate icebreaker: {}".format(str(e))}), 500


def update_icebreaker():
    try:
        icebreaker_message = request.json.get('iceBreaker')
        icebreaker_id = request.json.get('id')

        if not all([icebreaker_message, icebreaker_id]):
            return jsonify({"type": "error", "message": 'Missing required fields'}), 400
        
        existing_message = Icebreaker.find_one({"_id": ObjectId(icebreaker_id)})

        if not existing_message:
            return jsonify({"type": "error", "message": "Icebreaker does not exist"}), 404
        
        # Icebreaker.find_one_and_update({"_id": ObjectId(icebreaker_id)}, {"$set": {"content": icebreaker_message}})

        Icebreaker.insert_one({
            "content": icebreaker_message,
            "account": existing_message.get("account"),
            "contact": existing_message.get("contact"),
            "feedbacks": [],
            "context": existing_message.get("context"),
            "createdAt": datetime.now(timezone.utc),
            "generatedBy": existing_message.get("sales_owner")
        })

        return jsonify({"message": "Successfully updated Icebreaker!! "}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "Failed to update icebreaker: {}".format(str(e))}), 500


def delete_icebreaker(iceBreaker_id):
    try:
        ib_id = iceBreaker_id

        if not all([ib_id]):
            return jsonify({"type": "error","message": 'Missing required fields'}), 400
        
        existing_ib = Icebreaker.find_one({"_id":ObjectId(ib_id)})

        if not existing_ib:
            return jsonify({"type": "error","message": 'No such icebreaker found'}),404
        
        Icebreaker.find_one_and_delete({"_id":ObjectId(ib_id)})

        return jsonify({"message": "Successfully deleted Icebreaker!! "}), 200
    except Exception as e:
        return jsonify({"type": "error","message": "Failed to update icebreaker: {}".format(str(e))}), 500
from flask import jsonify,request
from db import db
from dotenv import load_dotenv
import os
from langchain_community.vectorstores import Pinecone as PineconeLC
from langchain_openai import OpenAIEmbeddings
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.runnables import RunnablePassthrough,RunnableParallel
from operator import itemgetter
from langchain.chains import LLMChain
import re
from datetime import datetime, timezone
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from langchain_google_genai import ChatGoogleGenerativeAI

Post = db[os.getenv("POST_COLLECTION_NAME")]
Post_Feedback = db[os.getenv("POST_FEEDBACK_CL")]

def generate_with_data():
    try:
        keywords_string = request.form.get('keywords')
        instructions = request.form.get('instruction') or "No specific instruction" 
        user = request.form.get('user_id')
        if not all([keywords_string, user]):
            return jsonify({"type":"error","message":"Please provide all the details"}),400
        
        embeddings = OpenAIEmbeddings()
        vectorstore = PineconeLC.from_existing_index("sales-bot", embeddings)
        filters = {
                "client":{"$eq": 'Blogs'}
            }
        retriever = vectorstore.as_retriever(search_type='similarity',
                                             search_kwargs={
                                                 'k': 10,
                                                 'filter': filters if filters is not None else {}
                                             }, )

        prompt = PromptTemplate.from_template("""                        
        Create an engaging LinkedIn post for a company called AlphaBI. 
        You are provided with blog data of AlphaBI as context, instructions and keywords to generate the post for LinkedIn.

        The post should extract key data from blogs provided as context.
        
        The post must:        
            -  emphasize on keywords
            -  use the provided context to generate the post. 
            -  Modify the message with your knowledge also to make it more engaging
        
        - Example tone:
            - Informative and educational
            - Solution-oriented
            - Engaging and persuasive
                                              
        - Optional:
            - Add a catchy line at the top of post to grab the attention of users scrolling through LinkedIn. The line should entice users to engage with the content. Consider using power words, posing questions, or highlighting benefits to make the post compelling.
            - Add a relevant question to spark discussion in the comments.
            - Include relevant hashtags like #DigitalTransformation #CustomSoftware #WebsiteDevelopment.
                                              
                                              
        Instructions:{instructions}
        context:{context}
        keywords:{keywords}
        """)

        doc_prompt = f"""
            get AlphaBI's past work or services related to these keywords {keywords_string}
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
                "instructions": itemgetter("instructions"),
                "keywords": itemgetter("keywords"),
            }
        ).assign(answer=rag_chain_from_docs)

        results = rag_chain_with_source.invoke({"context": documents,
                                                "instructions": instructions,
                                                "keywords": keywords_string})
        docs = results["context"]
        sources = []

        for doc in docs:    
            sources.append({
                "content": doc.page_content,
                "metadata": doc.metadata
            })

        results["context"] = sources

        pb = Post.insert_one({
            "content": results["answer"],
            "type":"data",
            "feedbacks": [],
            "context":results["context"],
            "createdAt": datetime.now(timezone.utc),
            "generatedBy": ObjectId(user)
        })

        return jsonify({"message":results.get('answer'), "_id":str(pb.inserted_id), "results":results.get("context")}), 200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500
    

def generate_with_ai():

    try:
        keywords = request.form.get('keywords')
        industry = request.form.get('industry')
        user = request.form.get('user_id')
        instructions = request.form.get('instruction') or "No instructions for now"

        if not all ([keywords,industry,user]):
            return jsonify({"type":"error", "message":"Please provide all the details"}),400
        
        # llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=1)
        llm = ChatGoogleGenerativeAI(model="gemini-pro")

        
        template = """
        Create an engaging LinkedIn Post. 
        - It should give insights about {industry} industry and should emphasize on the following keywords: {keywords}.
        - Get the potential ideas about innovation in {industry} and share knowledge about it also

        - Must:
            - Write the post from a general perspective.
            - Make sure that message does not look like an Advertisement by advertising about yourself.
            - Add relevant emojis at appropriate positions. 

        - Additionally you have follow this instruction: {instructions}.

        - Make sure the post highlights:-
            - Knowledge about the {industry} industry.

        - Example tone:
            - Informative and educational
            - Solution-oriented
            - Engaging and persuasive

        - Optional:
            - Do not provide headings to all section of the post
            - Add a catchy line at the top of post to grab the attention of users scrolling through LinkedIn. The line should entice users to engage with the content. Consider using power words, posing questions, or highlighting benefits to make the post compelling.
            - Add a relevant question to spark discussion in the comments.
            - Include relevant hashtags like #DigitalTransformation #CustomSoftware #WebsiteDevelopment.

          """


        prompt_template = PromptTemplate(input_variables=["keywords", "industry","instructions"],template=template) 



        class FactCheck(BaseModel):
            confidence_level: str = Field(description="The confidence level of llm for the post")
            post_status: str = Field(description="Whether the post can be posted on LinkedIn or not")
            references: str = Field(description="The list of references used to fact check the post")

        parser = JsonOutputParser(pydantic_object=FactCheck)

        fact_template = """
        {format_instructions}

        You are provided a LinkedIn Post.
        "{post}"  
        
        You have to check whether the the post is factually correct or not using cross references based on the information 
        provided in the post.

        In response, please provide:
        - Confidence Level: Indicate your confidence for the post using these categories:
            - True
            - Mostly True
            - Needs Verification
            - Likely False
            - False
        - Post status :  that will be one word answer 'yes' or 'no' based on the confidence level
        - References: Provide some latest links of the sites from where one can cross check the information provided in the post
        """
        fact_template_prompt=PromptTemplate(input_variables=["post"], template=fact_template, partial_variables={"format_instructions": parser.get_format_instructions()})

        

        reply = LLMChain(llm=llm, prompt=prompt_template, output_key='post')
        fact_check = LLMChain(llm=llm, prompt=fact_template_prompt, output_key='fact_check_ans', output_parser=parser)

        post = reply.invoke({"keywords":keywords, "industry":industry,"instructions":instructions})   
        fact_check_ans = fact_check.invoke({'post':post.get('post')})
        ans_dict = fact_check_ans.get('fact_check_ans')

        
        pb = Post.insert_one({
            "content": post.get('post'),
            "type":"ai",
            "feedbacks": [],
            "context":"",
            "createdAt": datetime.now(timezone.utc),
            "generatedBy": ObjectId(user)
        })
        return jsonify({"message":post.get('post'),
                        "confidence_level":ans_dict.get("confidence_level"),
                        "post_status":ans_dict.get("post_status"),
                        "references":ans_dict.get("references"),
                        "_id":str(pb.inserted_id)
                        }),200
    except Exception as e:
        return jsonify({"type": "error","message": "An unexpected error occurred: {}".format(str(e))}), 500
    

def post_feedback():
    try:
        post_id = request.json.get("post_id")
        post_content = request.json.get("post_content")
        sales_owner = request.json.get("sales_owner")
        sales_owner_id = request.json.get("sales_owner_id")
        value = int(request.json.get("value"))

        if value is None or value not in [-1, 0, 1]:
            return jsonify({"type": "error","message": f"Illegal feedback value: {value}"}), 400

        if post_id is None or sales_owner is None:
            return jsonify({"type": "error", "message": "Field 'post_id', 'sales_owner' is required"}), 500 

        fb = Post_Feedback.find_one_and_update({
            "_id": ObjectId(post_id),
            "sales_owner_id": ObjectId(sales_owner_id),
        }, {
            "$set": {
                "post_id":ObjectId(post_id),
                "content": post_content,
                "sales_owner": sales_owner,
                "sales_owner_id": ObjectId(sales_owner_id),
                "value": value
            }
        }, upsert=True, return_document=ReturnDocument.AFTER)

        Post.find_one_and_update({
            "_id": ObjectId(post_id)
        }, {
            "$addToSet": {
                "feedbacks": fb["_id"]
            }
        })

        return jsonify({"message": "Feedback Received", "data": {"_id": str(fb["_id"])}}), 200

    except Exception as e:
        print(e)
        return jsonify({"type": "error","message": "Failed to generate icebreaker feedback: {}".format(str(e))}), 500


def edit_post():
    try:
        post_message = request.json.get('post_message')
        post_id = request.json.get('post_id')

        if not all([post_message, post_id]):
            return jsonify({"type": "error", "message": 'Missing required fields'}), 400
        
        existing_message = Post.find_one({"_id": ObjectId(post_id)})

        if not existing_message:
            return jsonify({"type": "error", "message": "Post does not exist"}), 404
        

        context = existing_message.get("context") or ""
        new = Post.insert_one({
            "content": post_message,
            "feedbacks": [],
            "type":existing_message.get("type"),
            "context": context, 
            "createdAt": datetime.now(timezone.utc),
            "generatedBy": existing_message.get("generatedBy")
        })

        return jsonify({"message": "Successfully updated Post!! ", "data":{"_id": str(new.inserted_id)}}), 200
    except Exception as e:
        return jsonify({"type": "error", "message": "Failed to update post: {}".format(str(e))}), 500
    


# - Supporting Sources: List reliable sources that either support or contradict the claim. 
#             -Include:
#                 - Just Links to currently existing online articles, research papers, or reputable databases
                        # "Supporting Sources":ans_dict.get("Supporting Sources"),
#
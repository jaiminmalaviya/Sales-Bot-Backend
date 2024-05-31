from langchain_pinecone import PineconeVectorStore as PineconeLC
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders.text import TextLoader
from langchain_community.document_loaders import UnstructuredMarkdownLoader
from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone, PodSpec
from helpers.custom_error import CustomEmbedError
import os
from enum import Enum
from dotenv import load_dotenv
load_dotenv()


class FileType(Enum):
    TEXT = "txt"
    MD = "md"


def embed_text(content: str, file_type: str, client_name: str, document_metadata: dict, md_file_path: str = '',index_name = 'sales-bot') -> None:
    try:
        if file_type == "txt":
            uploads_folder = os.path.join(os.getcwd(), 'uploads', 'content')
            if not os.path.exists(uploads_folder):
                os.makedirs(uploads_folder)
            path = "uploads/content/{}.{}".format(client_name, file_type)

            # Save the contents temporarily to a file
            with open(path, "w", encoding="utf-8") as file:
                file.write(content)
            

        if file_type == "txt":
            loader = TextLoader(file_path=path, encoding = 'UTF-8')
        else:
            loader = UnstructuredMarkdownLoader(file_path=md_file_path)

        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=256, chunk_overlap=32)
        docs = text_splitter.split_documents(documents)

        # Add metadata to documents
        for doc in docs:
            doc.metadata["client"] = client_name
            for key in document_metadata.keys():
                doc.metadata[key] = document_metadata[key]

        # Initialize pinecone
        pc = Pinecone(
            api_key=os.getenv("PINECONE_API_KEY"),  # find at app.pinecone.io
        )
        
        # Free tier currently supports only one index
        # Could make the indexes more efficient with use of client names as indexes
        #
        # index_name = client_name
        
        if index_name not in [idx.name for idx in pc.list_indexes()]:
            pc.create_index(name=index_name, metric="cosine", dimension=1536,
                            spec=PodSpec(environment=os.getenv("PINECONE_ENV")))

        idx = pc.Index(index_name)
        embeddings = OpenAIEmbeddings()
        vectorstore = PineconeLC(idx, embeddings, "text")  # Do not change 'text' to anything else
        vectorstore.add_documents(docs)
        os.remove(md_file_path if file_type == 'md' else path)
    except Exception as e:
        raise CustomEmbedError("Something went wrong")
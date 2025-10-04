"""
1. Place any json or txt files you want to use in the `testimonials` folder.

2. Run the populate script:

   ```bash
   python populate_testimonials.py
   ```

   * This processes all json and txt files in `testimonials/`
   * Stores embeddings and indexes in the `chroma/testimonials` folder

"""

import argparse
import json
import os
import shutil
import logging

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema.document import Document
from langchain_chroma import Chroma

from llm_utils import get_embedding_function

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

FILE_DATA_PATH = "testimonials"
CHROMA_DB_PATH = "chromastore" + os.sep + "testimonials"
os.makedirs(CHROMA_DB_PATH, exist_ok=True)


def main():
    """
    Main function to process and populate ChromaDB with documents from the testimonials folder.
    Supports resetting the database with --reset flag.
    """
    # Check if the database should be cleared (using the --reset flag).
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true",
                        help="Reset the database.")
    args = parser.parse_args()
    if args.reset:
        logger.info("Clearing Database")
        clear_database()
    db = Chroma(
        persist_directory=CHROMA_DB_PATH, embedding_function=get_embedding_function()
    )

    chunk_size = 1200
    chunk_overlap = 200
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,  # Overlap to maintain context
        length_function=len)

    all_documents = []

    for file_name in os.listdir(FILE_DATA_PATH):

        file_ext = os.path.splitext(file_name)[1].lower()
        if file_ext == ".json" or file_ext == ".txt":
            file_path = os.path.join(FILE_DATA_PATH, file_name)
            print(f"Processing file: {file_path}")
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
                try:
                    data = json.loads(file_content)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Error decoding JSON from {file_path}: {e}, dumping as it is")
                file_content = file_content.replace(
                    "\n", " ").replace("\r", " ")
                text_chunks = text_splitter.split_text(file_content)
                # Create Document objects from chunks
                chunks = []
                for idx, chunk_text in enumerate(text_chunks):
                    chunk_doc = Document(
                        page_content=chunk_text,
                        metadata={
                            "source_file": file_name,
                            "file_path": str(file_path),
                            "original_size": len(file_content),
                            "chunk_index": idx,
                            "total_chunks": len(text_chunks)
                        }
                    )
                    chunks.append(chunk_doc)
                all_documents.extend(chunks)
                print(
                    f"\tCreated {len(chunks)} chunks from {file_name}, actual size: {len(file_content)} chars")
    print(f"\nTotal documents to add: {len(all_documents)}")

    # Add all documents to Chroma in batch
    if all_documents:
        print(f"\nAdding {len(all_documents)} documents to ChromaDB...")
        db.add_documents(all_documents)
        print(f"Successfully added all documents!")

    return len(all_documents)


def clear_database():
    """
    Clears the ChromaDB database directory.
    """
    if os.path.exists(CHROMA_DB_PATH):
        shutil.rmtree(CHROMA_DB_PATH)


if __name__ == "__main__":
    main()

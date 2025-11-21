import os
from dotenv import load_dotenv
from google import genai

def cleanup_all_stores():
    """
    Connects to the Google AI API and deletes all file search stores after user confirmation.
    """
    try:
        load_dotenv()
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            print("❌ Error: GOOGLE_API_KEY not found in .env file.")
            return

        print("--- Initializing Google AI Client ---")
        client = genai.Client(api_key=google_api_key)

        stores = list(client.file_search_stores.list())
        if not stores:
            print("✅ No file search stores found to delete.")
            return

        print("\nThe following file search stores will be PERMANENTLY DELETED:")
        for store in stores:
            print(f"  - {store.display_name} ({store.name})")

        confirm = input("\nAre you sure you want to delete all of these stores? (yes/no): ").lower().strip()

        if confirm != 'yes':
            print("\nAborted. No stores were deleted.")
            return

        print("\n--- Starting Deletion Process ---")
        for store in stores:
            try:
                print(f"Deleting store: {store.display_name} ({store.name})...")
                client.file_search_stores.delete(name=store.name, config={'force': True})
                print(f"✅ Deleted successfully.")
            except Exception as e:
                print(f"❌ Failed to delete {store.display_name}: {e}")
        
        print("\n--- Cleanup Complete ---")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    cleanup_all_stores()
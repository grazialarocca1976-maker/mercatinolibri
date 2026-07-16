import ricevute_condivise  
import json  

result = ricevute_condivise.list_receipts(bucket_name="ricevute", project_id=ricevute_condivise.PROJECT_ID, api_key=ricevute_condivise.CHIAVE_SUPABASE, limit=200)  
print(json.dumps(result, indent=2, ensure_ascii=False))
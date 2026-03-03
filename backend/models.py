import google.generativeai as genai
client = genai.Client(api_key="AIzaSyAVB0WiiWBdkMRbITaLr-27j_Gqbym7vfs")
models = client.models.list()
for model in models:
    print(model)

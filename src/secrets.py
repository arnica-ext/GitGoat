import os, pathlib, base64

class Secrets:
    
    def __init__(self):
        self.path = os.path.join(pathlib.Path().resolve(),'secrets')
        self.files = os.listdir(self.path)
        self.retrieved_files = []

    def get_next_secret(self) -> str:
        if len(self.files) == len(self.retrieved_files):
            self.retrieved_files = []
        for file in self.files:
            if file not in self.retrieved_files:
                self.retrieved_files.append(file)
                if not file.endswith(".encoded"):
                    continue
                with open(os.path.join(self.path, file),'r') as f:
                    content = f.read()
                    return Secrets.__get_secret_from_file_content(file, content)
    
    def __get_secret_from_file_content(file_name: str, file_content: str) -> str:
        for _ in range(3):
            file_content = base64.b64decode(file_content)
        return file_content.decode('utf-8')
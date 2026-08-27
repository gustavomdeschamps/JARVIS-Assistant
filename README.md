# JARVIS - Windows 10/11

## 1. Abra a pasta no VS Code

Abra a pasta `JARVIS`.

## 2. Crie o ambiente virtual

No terminal do VS Code:

```powershell
python -m venv .venv
```

## 3. Instale as dependências

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Depois:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 4. Execute

```powershell
.\.venv\Scripts\python.exe main.py
```

## 5. Teste

Primeiro pelo campo de texto:

- `teste de voz`
- `abrir calculadora`
- `abrir youtube`
- `abrir arquivos`

Depois por voz:

- `Jarvis`
- espere ele responder `Sim?`
- quando aparecer `Ouvindo`, diga `Abra o YouTube`

Também funciona direto:

- `Jarvis abra a calculadora`
- `Jarvis abra o YouTube`
- `Jarvis que horas são`
- `Jarvis pesquisar Java Spring Boot`

## Observações

- O reconhecimento de voz usa internet.
- A voz masculina principal usa `pt-BR-AntonioNeural`.
- Caso essa voz falhe, o programa tenta usar uma voz disponível no Windows.
- O Windows precisa detectar um microfone.
- Se o VS Code mostrar imports amarelos, selecione o interpretador:
  `Ctrl + Shift + P` -> `Python: Select Interpreter` -> `.venv\Scripts\python.exe`.

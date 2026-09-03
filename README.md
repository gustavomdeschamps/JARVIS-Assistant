# JARVIS — Intelligent Windows Assistant

JARVIS é um assistente pessoal para Windows 11 escrito em Python. Ele ouve,
entende linguagem natural em português, conversa, analisa informações reais
do computador e executa ações no Windows — sem exigir frases decoradas.

A ideia não é um sistema de comandos de voz com frases fixas, e sim um
assistente que interpreta o significado do que você está dizendo, usando um
modelo de linguagem rodando **100% local** via [Ollama](https://ollama.com).

```text
"Jarvis, quero programar um pouco."
  -> ele reconhece que você tem o VS Code instalado e abre.

"Jarvis, quanto é 15% de 340?"
  -> calcula e responde na hora, sem precisar do modelo de IA.

"Jarvis, me lembra em 20 minutos de tirar o bolo do forno."
  -> cria um lembrete e te avisa por voz quando o tempo passar.

"Jarvis, desliga o computador."
  -> ele pede confirmação antes de fazer algo irreversível.
```

---

## O que mudou nesta reformulação

A base original (interface 3D, reconhecimento de voz, roteador de intenção
via LLM local) foi mantida e reforçada. Por cima dela entrou uma camada
inteira de robustez e de capacidades novas:

- **Motor de decisão (brain) muito mais resiliente**: retry com backoff
  exponencial nas chamadas ao Ollama, reparo automático de JSON malformado
  (modelos pequenos às vezes cortam ou envolvem a resposta em texto), e um
  vocabulário de ações que passou de 16 para mais de 35.
- **Memória de verdade**: além do histórico curto de conversa, mensagens
  antigas são condensadas num resumo em vez de simplesmente esquecidas, e
  um novo módulo de **memória de longo prazo** guarda fatos sobre você
  ("meu nome é Gustavo") entre reinícios do programa.
- **Skills novas e testáveis**: calculadora segura, conversor de unidades,
  notas rápidas, temporizadores e lembretes com aviso por voz, e previsão
  do tempo — cada uma em seu próprio módulo, sem depender do LLM para
  fazer contas ou lembrar compromissos.
- **Ações de sistema mais poderosas, com segurança embutida**: fechar
  programas, ajustar brilho, capturar a tela, bloquear/suspender o PC — e
  **desligar/reiniciar sempre pedem confirmação explícita** antes de
  executar, para nunca derrubar trabalho não salvo por engano.
- **Logging de verdade**: em vez de `print()` espalhado, um logger
  centralizado grava em `data/logs/jarvis.log` (rotativo) e no console,
  para você conseguir depurar problemas de voz/IA depois que aconteceram.
- **Configuração via variáveis de ambiente**: qualquer valor de
  `config.py` pode ser sobrescrito com `JARVIS_<NOME>` sem editar código.
- **Suíte de testes automatizados** (129 testes, `unittest`, sem precisar
  de Windows, microfone ou Ollama rodando) cobrindo memória, skills,
  o parser/validador do brain e o fluxo de confirmação de ações
  destrutivas.
- **Repositório limpo**: cache de TTS (`.mp3`), `__pycache__` e os
  inventários de hardware/apps específicos da sua máquina não são mais
  versionados no git (ver `.gitignore`).

A camada visual (`ui/boot_screen.py`, `ui/core3d.py` — a tela de boot e o
núcleo 3D em OpenGL) **não foi alterada nesta rodada**: são ~3600 linhas de
renderização Qt/OpenGL que só podem ser validadas visualmente em uma
máquina Windows com GPU, o que este ambiente de desenvolvimento não tem.
Todo o esforço foi investido no "cérebro" e no controle do sistema, que são
testáveis e são o que realmente determina o quão inteligente e confiável o
assistente é.

---

## Arquitetura

```
main.py                    janela principal (Qt), loop de escuta contínua
config.py                  toda a configuração, com overrides via ambiente

core/
  logger.py                logging centralizado (console + arquivo rotativo)
  persistence.py            JSON store thread-safe e atômico (base de tudo
                            que persiste em disco)
  memory.py                 ConversationMemory (curto prazo + resumo)
                            LongTermMemory (fatos permanentes sobre o usuário)
  brain.py                  JarvisBrain: fala -> decisão estruturada (LLM local)
  commands.py               CommandSystem: decisão -> efeito real + resposta
  windows_controller.py     tudo que toca o Windows de fato (abrir/fechar
                            apps, volume, mídia, energia, brilho, screenshot)
  app_finder.py              indexação de aplicativos instalados
  system_scanner.py          inventário real de hardware/SO
  voice_engine.py / audio.py / stt.py / tts.py
                            captura de áudio, reconhecimento e síntese de voz

  skills/                   capacidades determinísticas, sem depender do LLM
    calculator.py            calculadora segura (AST, sem eval())
    converter.py              conversor de unidades (comprimento, massa,
                              volume, velocidade, temperatura)
    notes.py                  notas rápidas persistidas
    scheduler.py               temporizadores e lembretes com thread de
                              verificação em segundo plano
    weather.py                 previsão do tempo via wttr.in, com cache

tests/                      129 testes unitários (unittest), rodam em
                            qualquer SO, sem hardware/Ollama/rede reais
ui/
  boot_screen.py             tela de inicialização animada
  core3d.py                   núcleo 3D reativo em OpenGL (inalterado)
```

### Fluxo de uma frase

```
voz/texto do usuário
   │
   ▼
CommandSystem.execute(texto)
   │
   ├─ há uma confirmação pendente (desligar/reiniciar)? ────► trata aqui
   │  mesmo, sem chamar o modelo — mais seguro e mais rápido.
   │
   ▼
JarvisBrain.understand(texto)
   │  monta o prompt com: hardware real, apps instalados,
   │  fatos conhecidos sobre o usuário, resumo da conversa antiga
   │  e as últimas mensagens — pede ao Ollama uma decisão em JSON
   │  (schema fixo, com retry e reparo de JSON malformado).
   ▼
{action, target, query, amount, reply}
   │
   ▼
CommandSystem._route(...)
   │  despacha para o handler daquela ação: WindowsController,
   │  uma skill (calculadora, notas, timers, clima, ...), ou a
   │  memória de longo prazo — e monta a frase final de resposta.
   ▼
voz.speak(resposta) + brain.remember(texto, resposta)
```

---

## O que o JARVIS sabe fazer

**Aplicativos e janelas**: abrir/fechar programas instalados, abrir sites,
abrir pastas conhecidas (Downloads, Documentos, Desktop, ...), abrir as
Configurações do Windows.

**Web**: pesquisar no Google, pesquisar no YouTube.

**Mídia e volume**: subir/descer/mutar volume, play/pause, próxima/anterior.

**Sistema**: informações reais de CPU, RAM, GPU, disco, bateria e SO;
reindexar hardware e aplicativos; ajustar o brilho da tela; capturar a tela.

**Energia** (com confirmação de segurança): bloquear a tela, suspender,
**desligar** e **reiniciar** o computador — as duas últimas só executam
depois que você confirma explicitamente dizendo "confirmar" (ou cancela
dizendo "cancelar"); a confirmação expira sozinha em alguns segundos.

**Calculadora**: "quanto é 15% de 340", "raiz de 81", "12 vezes 8 mais 3" —
tudo avaliado com um parser seguro (AST), nunca com `eval()`.

**Conversor de unidades**: "10 quilômetros em milhas", "30 graus celsius em
fahrenheit", "2 quilos em libras" — comprimento, massa, volume, velocidade
e temperatura.

**Clima**: previsão do tempo atual, da sua cidade ou de qualquer outra.

**Notas**: "anota que preciso ligar pro dentista", "quais são minhas
notas", "apaga a última nota".

**Temporizadores e lembretes**: "toca um timer de 10 minutos", "me lembra
em 20 minutos de tirar o bolo do forno" — o JARVIS avisa por voz quando o
tempo termina, mesmo que você tenha mudado de assunto.

**Memória de longo prazo**: "meu nome é Gustavo" / "qual é o meu nome" —
fatos sobre você sobrevivem a reinícios do programa.

**Conversa geral**: qualquer pergunta ou papo que não seja uma das ações
acima é respondido normalmente pelo modelo local.

Diga "o que você sabe fazer" a qualquer momento para ouvir esse resumo.

---

## Instalação

### 1. Pré-requisitos

- Windows 11 (a camada de controle de sistema e voz é Windows-only).
- Python 3.11+.
- [Ollama](https://ollama.com) instalado e rodando (`ollama serve`).
- Um modelo baixado:
  ```
  ollama pull qwen3:1.7b
  ```

### 2. Dependências Python

```
pip install -r requirements.txt
```

### 3. Rodar

```
python main.py
```

---

## Configuração

Tudo em `config.py` tem um valor padrão sensato, e pode ser sobrescrito por
variável de ambiente com o prefixo `JARVIS_`, sem editar nenhum arquivo.
Alguns exemplos úteis:

| Variável                          | Para quê serve                                   |
|-----------------------------------|----------------------------------------------------|
| `JARVIS_PRIMARY_MODEL`            | Modelo Ollama usado para o roteamento de intenção   |
| `JARVIS_FALLBACK_MODEL`           | Modelo usado se o primário não estiver instalado    |
| `JARVIS_OLLAMA_HOST` / `_PORT`    | Endereço do servidor Ollama                         |
| `JARVIS_LOG_LEVEL`                | `DEBUG`, `INFO`, `WARNING`, `ERROR`                 |
| `JARVIS_LOG_TO_FILE`              | `true`/`false` — gravar log em `data/logs/`         |
| `JARVIS_CONFIRMATION_WORD`        | Palavra para confirmar desligar/reiniciar           |
| `JARVIS_CONFIRMATION_TIMEOUT_SECONDS` | Quanto tempo a confirmação fica pendente        |
| `JARVIS_WEATHER_CACHE_MINUTES`    | Cache da previsão do tempo                          |

Exemplo (PowerShell):

```powershell
$env:JARVIS_PRIMARY_MODEL = "llama3.2:3b"
$env:JARVIS_LOG_LEVEL = "DEBUG"
python main.py
```

---

## Testes

A suíte cobre memória, todas as skills, o parser/validador do brain e o
fluxo de confirmação de ações destrutivas — sem precisar de Windows,
microfone ou Ollama rodando:

```
python -m unittest discover -s tests -v
```

---

## Segurança

- Nenhuma ação executa comandos de terminal/PowerShell arbitrários gerados
  pelo modelo — o LLM só pode escolher entre uma lista fixa de ações.
- O modelo nunca inventa hardware, aplicativos ou fatos sobre o usuário:
  só usa o que foi realmente detectado na máquina.
- **Desligar** e **reiniciar** o computador exigem confirmação explícita,
  tratada de forma determinística (fora do LLM) e com expiração automática
  — uma resposta antiga de "sim" em outro contexto nunca aciona a ação.
- A calculadora nunca usa `eval()`: expressões são avaliadas por um
  interpretador de AST com lista branca de operações.

---

## Estrutura de dados persistidos (`data/`)

Tudo em `data/` é gerado localmente pela sua instalação e **não é
versionado no git** (ver `.gitignore`): inventário de hardware, índice de
aplicativos, cache de áudio do TTS, notas, temporizadores/lembretes,
fatos de longo prazo, capturas de tela e logs.

---

## Roadmap sugerido

- Extrair `ui/core3d.py` e `ui/boot_screen.py` em componentes menores e
  cobri-los com testes visuais (screenshot diffing) em uma máquina Windows.
- Suporte a múltiplos idiomas no roteador de intenção.
- Um painel de configurações na própria interface (hoje só via `config.py`
  / variáveis de ambiente).

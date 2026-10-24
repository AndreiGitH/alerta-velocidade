# Alerta de Velocidade — Manual

App Android que mostra sua velocidade num velocímetro estilo painel e **avisa por voz**
quando você passa dos seus limites, quando passa do limite da via e quando se aproxima
de um **radar** (a 200 m). Funciona em segundo plano, inclusive com o Google Maps ou o
Waze abertos.

---

## 1. Instalação

1. Abra a página [Releases](https://github.com/AndreiGitH/alerta-velocidade/releases)
   no celular e baixe o `app-debug.apk` da versão mais recente.
2. Toque no arquivo baixado. Se o Android bloquear, ative **"Permitir desta fonte"**.
3. Se o Play Protect avisar sobre "app desconhecido", toque em **Instalar mesmo assim**
   (o aviso aparece porque o app não vem da Play Store).

Para atualizar, basta instalar o APK novo por cima: os limites e as configurações
são mantidos.

## 2. Primeiro uso

1. Abra o app e toque em **Iniciar**.
2. Permita **Localização** ("Durante o uso do app") e **Notificações**.
3. Pronto: aparece a notificação fixa "Alerta de Velocidade" e o app passa a monitorar.
   Pode abrir o Maps; os avisos continuam.

> Os avisos saem pelo **volume de mídia**. Deixe-o alto. Enquanto o app fala, o som
> do Maps ou da música abaixa automaticamente.

## 3. A tela

| Elemento | O que mostra |
|---|---|
| **? (canto superior esquerdo)** | Abre o manual. |
| **+ (verde, ao lado do relógio)** | Marca um radar na posição atual: escolha 40, 50, 60, 80, 100, 110 ou digite a velocidade. Fica salvo só no celular. Também dá para marcar pela ação **+ Radar** da notificação, sem sair do Maps. Para revisar e apagar: ⚙ → **☰ Meus radares**. |
| **⚙ (canto superior direito)** | Abre as Configurações (inclui **⟳ Atualizar radares**). |
| **Velocímetro** | Ponteiro e velocidade no centro. Faixas **verde** (abaixo do Limite 1), **laranja** (entre o Limite 1 e o 2) e **vermelha** (a partir do Limite 2). O número da velocidade fica laranja/vermelho quando você passa do limite. Embaixo, o **relógio**. |
| **Faixa vermelha "⚠ Radar a 150 m · 60 km/h"** | Aparece só quando há um radar à frente a até 200 m. |
| **Placa da via** | Limite da via onde você está (TomTom ou OpenStreetMap) e o nome da rua. |
| **Limite 1, 2 e 3** | Seus limites em km/h. Ajuste com **− / +** (de 5 em 5) ou digitando. |
| **Iniciar / Parar** | Liga e desliga o monitoramento. |

Os limites e as Configurações só podem ser alterados com o alerta **parado**.

## 4. Os avisos

### Limites de velocidade
- Ao passar de um limite, o app **fala o número** ("sessenta", "oitenta"...).
- Há voz para **30, 40, 50, 60, 70, 80, 90, 100, 110 e 120**. Para outros valores
  (ex.: 65), toca bipes: 1 bipe no Limite 1, 2 no Limite 2, 3 no Limite 3.
- O aviso de um limite só se repete depois que você desce **3 km/h abaixo** dele e
  volta a passar. Isso evita repetição enquanto você anda perto do limite.

### Limite da via
- Com **"Usar limite da via"** ligado (Configurações), o app consulta o limite da rua
  a cada 10 s ou 150 m. Quando encontra, os avisos passam a seguir o limite da via
  (laranja nos 10 km/h antes dele, vermelho a partir dele).
- Sem limite cadastrado para a via, o app volta aos seus 3 limites.
- Para ignorar o limite da via, ligue **Forçar meus limites**.

### Radares
- Quando um radar **à sua frente** chega a **200 m**, o app fala
  **"Radar 200 metros"** seguido do limite do radar (ex.: "sessenta").
- Cada radar é avisado uma vez; o do sentido oposto, ao lado, não repete o aviso.
- Fontes oficiais incluídas (cerca de 1.340 radares):

| Fonte | Cobertura |
|---|---|
| ANTT | Rodovias federais concedidas (pedagiadas), todo o Brasil |
| SEINFRA-BA | Rodovias estaduais da Bahia |
| Transalvador | Cidade de Salvador |

> Não estão incluídos radares do DNIT (federais sem concessão), de outros DERs
> estaduais e de outras prefeituras. Radares móveis e de semáforo também não.

## 5. Configurações (⚙)

| Opção | Para que serve |
|---|---|
| **Usar limite da via (TomTom / OpenStreetMap)** | Liga a consulta do limite da rua. |
| **Avisar radares a 200 m** | Liga o aviso de radares. |
| **Forçar meus limites** | Ligada: os avisos usam sempre os seus 3 limites, mesmo se houver limite da via. |
| **Chave da API TomTom** | Opcional. Melhora muito o limite da via (veja abaixo). Fica salva só no celular e aparece oculta. |
| **▶ Testar vozes** | Toca as vozes dos seus 3 limites, para conferir o som. |

Toque em **Salvar** para guardar ou **Cancelar** para desfazer.

### Como obter a chave TomTom (grátis)
1. Crie uma conta em <https://developer.tomtom.com>.
2. No painel, em **Keys**, copie a chave (precisa ter acesso à *Search API*).
3. Cole em ⚙ → **Chave da API TomTom** → **Salvar**.

O plano gratuito dá 2.500 consultas por dia (cerca de 7 horas de direção).
Sem a chave, o app usa só o OpenStreetMap, que tem poucos limites cadastrados no Brasil.

## 6. Problemas comuns

| Sintoma | O que fazer |
|---|---|
| Velocidade fica em "--" | Aguarde o sinal de GPS (céu aberto ajuda). Confira se a Localização do celular está ligada. |
| Não ouço os avisos | Aumente o **volume de mídia**. Use ⚙ → **Testar vozes**. |
| Avisa um número diferente dos meus limites | Está valendo o limite da via. Ligue **Forçar meus limites**. |
| Um limite não foi falado | Ele já tinha sido avisado e você não desceu 3 km/h abaixo dele; ou não há voz para esse valor (toca bipes). |
| "Chave inválida" / "cota diária esgotada" | Confira a chave TomTom. Enquanto isso o app usa o OpenStreetMap. |
| O app para sozinho | Em Configurações do Android → Apps → Alerta de Velocidade → Bateria, escolha **Sem restrições**. |

---

## 7. Para quem mantém o projeto

### Como o APK é gerado
Todo `push` no GitHub roda o workflow [`.github/workflows/build.yml`](.github/workflows/build.yml),
que monta o projeto Android, compila e publica o APK em Releases. O código Java do app
está dentro desse arquivo.

### Vozes
Arquivos em [`audio/`](audio/), em MP3:
- `NN.mp3` — fala o número NN (ex.: `60.mp3` → "sessenta").
- `radar.mp3` — "Radar 200 metros".

Para adicionar uma velocidade, coloque `audio/NN.mp3` e faça push. Para converter de WAV:

```bash
ffmpeg -i 65.wav -ac 1 -ar 24000 -codec:a libmp3lame -b:a 48k audio/65.mp3
```

### Atualizar os radares
É automático. O workflow [`.github/workflows/radares.yml`](.github/workflows/radares.yml)
roda toda segunda-feira (ou em **Actions → Atualizar radares → Run workflow**) e:

1. baixa o CSV mais recente da ANTT;
2. lê o mapa oficial da Transalvador;
3. baixa o `Mapa-Radar_*.rar` mais recente da
   [página da SEINFRA-BA](https://www.ba.gov.br/infraestrutura/12046/mapas), extrai o KML
   e grava por cima de `dados/radares_ba_seinfra.kml`;
4. gera `dados/radares.csv`, faz commit se mudou e mostra a tabela de radares por fonte
   no resumo da execução.

Se uma fonte falhar, os radares dela da versão anterior são mantidos. No app, o botão
**⚙ → ⟳ Atualizar radares** baixa esse `radares.csv` direto do repositório.

Para rodar no computador (precisa do 7-Zip instalado):

```bash
python dados/gerar_radares.py
```

O manual do app em HTML fica em [`docs/manual.html`](docs/manual.html) e abre pelo botão **?** do app.

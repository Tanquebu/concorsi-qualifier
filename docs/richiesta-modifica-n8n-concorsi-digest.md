# Richiesta modifica workflow n8n — concorsi-digest

> Da girare sulla sessione intake.
> Workflow: `concorsi-digest` (ID: `hJDHp2IVCcLhFB58`) — istanza n8n di intake.

---

## Problema

Il nodo `send-telegram` fallisce con `Bad Request: text is too long` (esecuzione 743, 12/06/2026).
Telegram impone un limite di **4096 caratteri** per messaggio.
Il payload attuale invia tutti i bandi compatibili in un unico testo: su 513 bandi il limite viene superato abbondantemente.

---

## Soluzione adottata lato Python (già implementata)

Il modulo `notifier` di concorsi-qualifier invia ora un payload JSON strutturato che separa i bandi per livello di compatibilità:

```json
{
  "data": "2026-06-12",
  "totale": 513,
  "alta": [
    {
      "titolo": "Concorso pubblico n. 3 posti Informatico cat. D",
      "ente": "Comune di Milano",
      "scadenza": "2026-07-15",
      "url": "https://portale.inpa.gov.it/concorso/...",
      "compatibilita": "alta"
    }
  ],
  "media": [
    { "titolo": "...", "ente": "...", "scadenza": "...", "url": "...", "compatibilita": "media" },
    ...
  ]
}
```

---

## Modifiche richieste al workflow n8n

### 1. Aggiornare il nodo che costruisce il testo Telegram

Il messaggio deve avere questa struttura:

```
📋 Digest Concorsi — 12/06/2026
Bandi compatibili: 513 (✅ 10 alta | 🟡 503 media)

✅ ALTA COMPATIBILITÀ

• Concorso pubblico n. 3 posti Informatico cat. D
  Comune di Milano | Scadenza: 15/07/2026
  🔗 https://portale.inpa.gov.it/concorso/...

[altri bandi alta...]

🟡 503 bandi di media compatibilità entro 30 giorni.
```

Logica:
- Header fisso: data + conteggi per livello
- Sezione `alta` in dettaglio: titolo, ente, scadenza, link
- Sezione `media`: solo conteggio (niente dettagli — troppi e meno urgenti)

### 2. Gestire il limite 4096 caratteri (robustezza futura)

Anche con solo i bandi `alta` in dettaglio, in futuro potrebbero esserci molti bandi alta. Prevedere uno split:

- Se il testo supera 4096 caratteri, spezzarlo in più messaggi
- Approccio consigliato in n8n: nodo **Code** che splitta in array di chunk ≤ 4096 char (spezzare su newline, non a metà parola), poi **Loop Over Items** → `send-telegram` per ciascun chunk

### 3. Variabili d'ambiente utilizzate

Il workflow usa già `CONCORSI_BOT_TOKEN` e `TELEGRAM_CHAT_ID` configurati nel `.env` di intake. Nessuna nuova variabile necessaria.

---

## Note operative

- Il notifier Python invia POST a `http://localhost:5678/webhook/concorsi-digest`
- Il vecchio campo `bandi` (lista flat) non esiste più nel payload — il workflow va aggiornato di conseguenza
- I test del notifier Python sono stati aggiornati per il nuovo formato payload

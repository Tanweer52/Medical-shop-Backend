# Medical Shop Backend

FastAPI backend for the medical shop POS/ERP system.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the server:
   ```bash
   uvicorn main:app --reload
   ```

The API will be available at http://127.0.0.1:8000

## Endpoints

- `GET /medicines` - Get all medicines
- `POST /medicines/{id}/add-stock` - Add stock to a medicine
- `GET /medicines/summary` - Get summary data (low stock, expiring, etc.)

## API Documentation

Visit http://127.0.0.1:8000/docs for interactive API docs.
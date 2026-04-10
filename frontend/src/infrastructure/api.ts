import axios from 'axios';

// Utiliza por padrão a porta 8000 da API FastAPI caso não seja especificada nas vars de ambiente
const baseURL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const api = axios.create({
  baseURL,
  headers: {
    "Content-Type": "application/json",
  },
});

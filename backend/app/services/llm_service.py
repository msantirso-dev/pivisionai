"""LLM vision analysis: Ollama (local) and OpenAI (ChatGPT)."""

import base64
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.services.llm_config import load_llm_config

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = """Sos un analista de videovigilancia para centros de monitoreo.
Analizá la imagen del evento y respondé SOLO en JSON válido con este formato:
{
  "summary": "reseña breve en español (1-2 oraciones) de lo que ocurre en la imagen",
  "person_detected": true,
  "person_clothing": "si hay persona: colores, prendas, calzado, gorra, mochila, uniforme, etc. Si no hay persona visible, null",
  "person_description": "edad aparente, postura, acción que realiza (ej. caminando, merodeando)",
  "scene_description": "descripción general de la escena",
  "context_evaluation": "evaluación según el contexto de la regla, si fue provisto",
  "threat_level": "none|low|medium|high|critical",
  "objects_detected": ["persona", "vehículo"],
  "false_positive_risk": "low|medium|high",
  "recommended_action": "acción sugerida para el operador",
  "confidence": 0.0
}
Reglas:
- Si hay personas visibles, person_clothing es OBLIGATORIO y debe ser específico.
- Priorizá lo solicitado en el contexto de la regla en summary y context_evaluation.
- Sé concreto, en español rioplatense, orientado al operador de seguridad."""


class LLMVisionService:
    async def analyze_image_file(
        self,
        image_path: str,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        path = Path(image_path)
        if not path.exists():
            return {"success": False, "error": "Imagen no encontrada"}

        image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        return await self.analyze_image_base64(image_b64, context, config)

    async def analyze_image_base64(
        self,
        image_b64: str,
        context: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        cfg = config or await load_llm_config()
        if not cfg.get("enabled"):
            return {"success": False, "error": "LLM deshabilitado"}

        provider = (cfg.get("provider") or "none").lower()
        context = context or {}
        user_prompt = self._build_user_prompt(context)

        try:
            if provider == "ollama":
                result = await self._analyze_ollama(image_b64, user_prompt, cfg)
            elif provider == "openai":
                result = await self._analyze_openai(image_b64, user_prompt, cfg)
            else:
                return {"success": False, "error": f"Proveedor LLM no soportado: {provider}"}

            return {
                "success": True,
                "provider": provider,
                "model": result.get("model"),
                "analysis": result.get("text"),
                "parsed": result.get("parsed"),
                "raw": result.get("raw"),
            }
        except Exception as e:
            logger.error("LLM analysis failed: %s", e)
            return {"success": False, "error": str(e), "provider": provider}

    def _build_user_prompt(self, context: Dict[str, Any]) -> str:
        parts = ["Analizá esta imagen de cámara de seguridad."]
        if context.get("camera_name"):
            parts.append(f"Cámara: {context['camera_name']}")
        if context.get("location"):
            parts.append(f"Ubicación: {context['location']}")
        if context.get("event_type"):
            parts.append(f"Tipo de evento: {context['event_type']}")
        if context.get("object_class"):
            parts.append(f"Objeto detectado por YOLO: {context['object_class']}")
        if context.get("rule_name"):
            parts.append(f"Regla: {context['rule_name']}")
        if context.get("context_description"):
            parts.append(
                f"Contexto de la regla (qué se busca identificar o validar): {context['context_description']}"
            )
            parts.append(
                "Evaluá la imagen según ese contexto. Indicá en context_evaluation si se cumple o no."
            )
        elif context.get("object_class") == "person":
            parts.append(
                "Hay alerta de persona: describí en detalle vestimenta, accesorios y qué está haciendo."
            )
        if context.get("description"):
            parts.append(f"Alerta automática previa: {context['description']}")
        parts.append("Respondé en JSON con summary, person_clothing (si hay persona) y context_evaluation.")
        return "\n".join(parts)

    async def _analyze_ollama(self, image_b64: str, user_prompt: str, cfg: Dict) -> Dict:
        base_url = cfg.get("ollama_base_url", "http://localhost:11434").rstrip("/")
        model = cfg.get("ollama_model", "llava")
        system_prompt = cfg.get("system_prompt") or DEFAULT_PROMPT

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt, "images": [image_b64]},
            ],
            "stream": False,
            "options": {"num_predict": cfg.get("max_tokens", 800)},
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{base_url}/api/chat", json=payload)
            if response.status_code == 404:
                raise ValueError(
                    f"Modelo '{model}' no encontrado en Ollama. "
                    f"Ejecute en el servidor: ollama pull {model}"
                )
            if response.status_code >= 400:
                detail = response.text[:300]
                raise ValueError(f"Ollama error {response.status_code}: {detail}")
            response.raise_for_status()
            data = response.json()
            text = data.get("message", {}).get("content", "")
            return {
                "model": model,
                "text": text,
                "parsed": self._try_parse_json(text),
                "raw": data,
            }

    async def _analyze_openai(self, image_b64: str, user_prompt: str, cfg: Dict) -> Dict:
        api_key = cfg.get("openai_api_key")
        if not api_key:
            raise ValueError("OPENAI_API_KEY no configurada")

        model = cfg.get("openai_model", "gpt-4o-mini")
        base_url = (cfg.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/")
        system_prompt = cfg.get("system_prompt") or DEFAULT_PROMPT

        payload = {
            "model": model,
            "max_tokens": cfg.get("max_tokens", 800),
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                    ],
                },
            ],
        }

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{base_url}/chat/completions", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            return {
                "model": model,
                "text": text,
                "parsed": self._try_parse_json(text),
                "raw": data,
            }

    async def test_connection(self, config: Optional[Dict] = None) -> Dict[str, Any]:
        cfg = config or await load_llm_config()
        provider = (cfg.get("provider") or "").lower()

        if provider == "ollama":
            base_url = cfg.get("ollama_base_url", "http://localhost:11434").rstrip("/")
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(f"{base_url}/api/tags")
                r.raise_for_status()
                models = [m.get("name") for m in r.json().get("models", [])]
                model = cfg.get("ollama_model", "llava")
                available = any(model in m or m.startswith(f"{model}:") for m in models)
                vision_hints = [m for m in models if any(v in m.lower() for v in ("llava", "vision", "moondream", "bakllava"))]
                msg = f"Ollama conectado. Modelos: {', '.join(models[:8])}"
                if not available:
                    msg += f". ⚠ El modelo '{model}' NO está instalado. Ejecute: ollama pull {model}"
                    if vision_hints:
                        msg += f". Modelos visión disponibles: {', '.join(vision_hints[:3])}"
                return {
                    "success": True,
                    "message": msg,
                    "model_available": available,
                    "models": models,
                }

        if provider == "openai":
            api_key = cfg.get("openai_api_key")
            if not api_key:
                return {"success": False, "message": "API key de OpenAI no configurada"}
            base_url = (cfg.get("openai_base_url") or "https://api.openai.com/v1").rstrip("/")
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                r.raise_for_status()
                return {"success": True, "message": "OpenAI API conectada correctamente"}

        return {"success": False, "message": "Seleccioná un proveedor (ollama u openai)"}

    def _try_parse_json(self, text: str) -> Optional[Dict]:
        import json
        import re

        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None


llm_vision_service = LLMVisionService()

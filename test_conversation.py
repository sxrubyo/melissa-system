#!/usr/bin/env python3
"""
Conversación de prueba con Melissa - Simula un lead real
"""
import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import melissa as melissa_module
from melissa import Config

async def chat_with_melissa(message: str, user_id: str = "human_test"):
    """Envía un mensaje a Melissa y retorna la respuesta"""
    try:
        melissa = melissa_module.melissa
        
        if melissa is None:
            await melissa_module.init_melissa()
        
        # Llamar process_message
        result = await melissa.process_message(
            message=message,
            chat_id=user_id,
            platform="telegram",
            sender_name="Lead de Prueba"
        )
        
        # Extraer la respuesta
        if isinstance(result, dict):
            return result.get("response", result.get("message", str(result)))
        return str(result)
    except Exception as e:
        import traceback
        return f"Error: {e}\n{traceback.format_exc()}"

async def main():
    print("💬 CONVERSACIÓN CON MELISSA - MODO DEMO")
    print("=" * 50)
    
    user_id = "human_lead_demo_001"
    
    # Mensaje inicial - lead que no sabe qué es Melissa
    messages = [
        "Hola, me llegó un link de ti pero no sé qué es esto",
    ]
    
    for msg in messages:
        print(f"\n👤 LEAD: {msg}")
        response = await chat_with_melissa(msg, user_id)
        print(f"\n🤖 MELISSA: {response}")
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
"""Se ejecuta el Runner real del SDK con respuestas de modelo deterministas.

No usa API keys ni servicios externos; las herramientas y handoffs sí corren.
"""
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from agents import Model, ModelResponse, Usage, MaxTurnsExceeded
from openai.types.responses import ResponseFunctionToolCall, ResponseOutputMessage, ResponseOutputText

from decentralized.main import Conversation
from decentralized.agents import build_agents
from shared import bookings, faqs, weather_service
from shared.weather_contracts import WeatherReading


class ScriptedModel(Model):
    def __init__(self, steps):
        self.steps = iter(steps)
        self.inputs = []
        self.counter = 0

    async def get_response(self, *args, **kwargs):
        self.inputs.append(kwargs.get('input', args[1] if len(args) > 1 else None))
        step = next(self.steps)
        self.counter += 1
        if isinstance(step, tuple):
            name, arguments = step
            output = ResponseFunctionToolCall(type='function_call', name=name,
                arguments=json.dumps(arguments), call_id=f'call_{self.counter}', id=f'fc_{self.counter}')
        else:
            output = ResponseOutputMessage(id=f'msg_{self.counter}', type='message', role='assistant',
                status='completed', content=[ResponseOutputText(type='output_text', text=step, annotations=[])])
        return ModelResponse(output=[output], usage=Usage(), response_id=f'resp_{self.counter}')

    async def stream_response(self, *args, **kwargs):
        raise NotImplementedError
        yield


def test_real_handoffs_weather_booking_and_conversation_state(monkeypatch, tmp_path, capsys):
    target = (datetime.now(ZoneInfo('America/Guatemala')).date() + timedelta(days=1)).isoformat()
    monkeypatch.setenv('BOOKINGS_DB', str(tmp_path/'bookings.sqlite3'))
    reading = WeatherReading(10, 20, 0, 10, 24)
    monkeypatch.setattr(weather_service, 'get_weather_reading', lambda _: (reading, None))
    checked = []
    def weather(date):
        checked.append(date)
        return reading
    monkeypatch.setattr(bookings, 'fetch_weather_reading', weather)
    monkeypatch.setattr(faqs, 'search_faqs', lambda _: [{'faq_id': 'FAQ-001', 'answer': 'Zona de salto'}])
    model = ScriptedModel([
        ('transfer_to_agente_clima', {}), ('consultar_clima', {'fecha_iso': target}),
        ('transfer_to_agente_reservas', {}),
        '¿Cuál es tu nombre y a qué hora deseas la cita?',
        ('calendarizar_cita', {'fecha_iso': target, 'nombre_cliente': 'Ana', 'hora': '09:00'}),
        'Cita registrada.',
        ('transfer_to_agente_faqs', {}), ('buscar_faq', {'pregunta': '¿Dónde se ubica la zona de salto?'}),
        'Zona de salto [FAQ-001].',
    ])
    conversation = Conversation(model=model)
    conversation.reply(f'Quiero reservar el {target}')
    assert conversation.active_agent.name == 'Agente Reservas'
    conversation.reply('Mi nombre es Ana, a las 09:00.')
    assert checked == [target]
    serialized = json.dumps(conversation.history, ensure_ascii=False)
    assert target in serialized and 'Ana' in serialized and 'confirmada' in serialized
    conversation.reply('¿Dónde se ubica la zona de salto?')
    assert conversation.active_agent.name == 'Agente FAQs'
    assert 'FAQ-001' in json.dumps(conversation.history)
    assert '[handoff] Agente Clima -> Agente Reservas' in capsys.readouterr().out


def test_handoff_loop_is_bounded():
    model = ScriptedModel([('transfer_to_agente_clima', {}), ('transfer_to_agente_faqs', {})] * 10)
    conversation = Conversation(model=model, trace=False)
    with pytest.raises(MaxTurnsExceeded):
        conversation.reply('Hola')
    assert conversation.history == []


@pytest.mark.parametrize('results', [[], [{'faq_id': 'FAQ-002', 'answer': 'Evidencia'}]])
def test_faq_tool_result_reaches_sdk_model(monkeypatch, results):
    monkeypatch.setattr(faqs, 'search_faqs', lambda _: results)
    model = ScriptedModel([('buscar_faq', {'pregunta': 'Consulta'}), 'Respuesta'])
    conversation = Conversation(model=model, trace=False)
    conversation.reply('Consulta')
    outputs = [item for item in conversation.history if item.get('type') == 'function_call_output']
    data = json.loads(outputs[0]['output'])
    assert data['resultados'] == results
    assert data['sin_evidencia'] == (not results)


def test_faq_error_is_explicit(monkeypatch):
    def fail(_):
        raise RuntimeError('private connection details')
    monkeypatch.setattr(faqs, 'search_faqs', fail)
    model = ScriptedModel([('buscar_faq', {'pregunta': 'Consulta'}), 'No disponible'])
    conversation = Conversation(model=model, trace=False)
    conversation.reply('Consulta')
    data = json.dumps(conversation.history)
    assert 'No se pudo consultar' in data
    assert 'private connection details' not in data


def test_graph_has_peer_handoffs_and_no_manager_tools():
    agents = build_agents()
    assert [a.name for a in agents['faq'].handoffs] == ['Agente Clima']
    assert {a.name for a in agents['clima'].handoffs} == {'Agente FAQs', 'Agente Reservas'}
    assert {a.name for a in agents['reservas'].handoffs} == {'Agente FAQs', 'Agente Clima'}
    assert [t.name for t in agents['reservas'].tools] == ['calendarizar_cita']


def test_existing_architectures_use_shared_integrations():
    from centralized.faq_agent import faq_agent as cf
    from hierarchical.faq_agent_stub import faq_agent as hf
    from centralized.booking_agent import booking_agent as cb
    from hierarchical.booking_agent_stub import booking_agent as hb
    from shared.agent_tools import buscar_faq, calendarizar_cita
    assert cf.tools == hf.tools == [buscar_faq]
    assert cb.tools == hb.tools == [calendarizar_cita]

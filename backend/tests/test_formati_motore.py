"""
Verifica del percorso completo dell'estensione ai video lunghi, con le
risposte dell'API simulate: la quota YouTube e' un budget giornaliero e non
va spesa per i test.

Quello che si vuole dimostrare e' una cosa sola: dalla stessa risposta
dell'API escono due baseline separate, e quella degli Short non cambia per
effetto dei video lunghi dello stesso canale.
"""

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def motore(monkeypatch):
    """vpi_engine con le dipendenze pesanti neutralizzate."""
    for nome in ('apscheduler', 'apscheduler.schedulers',
                 'apscheduler.schedulers.background'):
        monkeypatch.setitem(sys.modules, nome, types.ModuleType(nome))
    sched = sys.modules['apscheduler.schedulers.background']
    sched.BackgroundScheduler = object
    import vpi_engine
    return vpi_engine


class _Risposta:
    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload

    def json(self):
        return self._payload


def _api_finta(video):
    """Simula le tre chiamate di get_channel_video_samples."""
    def get(url, **kwargs):
        if '/channels?' in url:
            return _Risposta({'items': [{'contentDetails': {
                'relatedPlaylists': {'uploads': 'UU_test'}}}]})
        if '/playlistItems?' in url:
            return _Risposta({'items': [
                {'contentDetails': {'videoId': v['id']}} for v in video]})
        if '/videos?' in url:
            return _Risposta({'items': [{
                'id': v['id'],
                'contentDetails': {'duration': v['durata']},
                'statistics': {'viewCount': str(v['views'])},
                'snippet': {'publishedAt': '2026-08-01T00:00:00Z'},
            } for v in video]})
        raise AssertionError(f'chiamata inattesa: {url}')
    return get


def test_i_campioni_escono_divisi_per_formato(motore, monkeypatch):
    video = (
        [{'id': f's{i}', 'durata': 'PT45S', 'views': 3000} for i in range(6)] +
        [{'id': f'l{i}', 'durata': 'PT12M30S', 'views': 400000} for i in range(7)]
    )
    monkeypatch.setattr(motore.requests, 'get', _api_finta(video))

    campioni = motore.get_channel_video_samples('UC_qualsiasi')
    assert campioni is not None
    assert len(campioni['SHORT']) == 6
    assert len(campioni['LONG']) == 7


def test_la_baseline_short_non_cambia_aggiungendo_video_lunghi(motore, monkeypatch):
    """
    Lo stesso canale, misurato due volte: la seconda ha nove video lunghi in
    piu'. La baseline degli Short deve essere identica.
    """
    short = [{'id': f's{i}', 'durata': 'PT50S', 'views': 2500} for i in range(6)]
    lunghi = [{'id': f'l{i}', 'durata': 'PT20M', 'views': 500000} for i in range(9)]

    monkeypatch.setattr(motore.requests, 'get', _api_finta(short))
    solo_short = motore.get_channel_video_samples('UC_a')
    base_a, _ = motore.baseline_from_samples(solo_short['SHORT'])

    monkeypatch.setattr(motore.requests, 'get', _api_finta(short + lunghi))
    misto = motore.get_channel_video_samples('UC_b')
    base_b, _ = motore.baseline_from_samples(misto['SHORT'])
    base_long, _ = motore.baseline_from_samples(misto['LONG'])

    assert base_a == base_b == 2500.0
    assert base_long == 500000.0


def test_durate_non_utilizzabili_non_entrano_in_nessun_formato(motore, monkeypatch):
    """Dirette e premiere arrivano con durata P0D o PT0S: vanno scartate."""
    video = [
        {'id': 's1', 'durata': 'PT30S', 'views': 100},
        {'id': 'x1', 'durata': 'P0D', 'views': 999999},
        {'id': 'x2', 'durata': '', 'views': 999999},
        {'id': 'l1', 'durata': 'PT8M', 'views': 5000},
    ]
    monkeypatch.setattr(motore.requests, 'get', _api_finta(video))
    campioni = motore.get_channel_video_samples('UC_c')
    assert [c['video_id'] for c in campioni['SHORT']] == ['s1']
    assert [c['video_id'] for c in campioni['LONG']] == ['l1']


def test_la_cache_serve_entrambi_i_formati_con_una_sola_lettura(motore, monkeypatch):
    """
    Il punto economico dell'implementazione: misurare uno Short e un video
    lungo dello stesso canale non deve costare due letture dell'API.
    """
    video = (
        [{'id': f's{i}', 'durata': 'PT40S', 'views': 1000} for i in range(6)] +
        [{'id': f'l{i}', 'durata': 'PT15M', 'views': 90000} for i in range(6)]
    )
    chiamate = {'n': 0}
    reale = _api_finta(video)

    def conta(url, **kwargs):
        if '/channels?' in url:
            chiamate['n'] += 1
        return reale(url, **kwargs)

    monkeypatch.setattr(motore.requests, 'get', conta)
    motore._BASELINE_CACHE.set('UC_d', None)   # assicura che la voce non esista
    try:
        motore._BASELINE_CACHE._dati.pop('UC_d', None)
    except AttributeError:
        pass

    base_short, _ = motore._cached_channel_baseline('UC_d', 'SHORT')
    base_long, _ = motore._cached_channel_baseline('UC_d', 'LONG')

    assert base_short == 1000.0
    assert base_long == 90000.0
    assert chiamate['n'] == 1, 'la seconda baseline deve venire dalla cache'

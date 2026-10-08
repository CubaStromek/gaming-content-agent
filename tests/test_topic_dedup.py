"""
Testy pro topic_dedup — hlavně líná LLM druhá vrstva
(fallback kandidáti: publikuj další v pořadí, když top témata jsou duplicitní
nebo nejdou napsat).
"""

from itertools import islice
from unittest.mock import patch

import topic_dedup


def _topic(name):
    return {'topic': name, 'title': name, 'game_name': name}


RECENT = [{'topic': 'Staré téma', 'title': 'Staré téma', 'timestamp': '2026-07-09T08:00:00', 'game_name': ''}]


class TestIterLlmUniqueTopics:
    def test_checks_only_candidates_the_caller_takes(self):
        """Kandidát se LLM kontroluje, až když si o něj volající řekne."""
        topics = [_topic(f'T{i}') for i in range(5)]
        calls = []

        def fake_is_same_story(client, topic, recent):
            calls.append(topic['topic'])
            return (None, '')  # nic není duplicita

        with patch.object(topic_dedup, 'get_recent_published_topics', return_value=RECENT), \
             patch.object(topic_dedup, '_llm_is_same_story', fake_is_same_story), \
             patch('anthropic.Anthropic'):
            taken = list(islice(topic_dedup.iter_llm_unique_topics(topics), 2))

        assert [t['topic'] for t in taken] == ['T0', 'T1']
        assert calls == ['T0', 'T1']  # T2–T4 se nekontrolovaly (ušetřená volání)

    def test_duplicates_are_skipped_and_reported(self):
        """Duplicitní top témata se přeskočí, nahradí je další kandidáti v pořadí."""
        topics = [_topic(f'T{i}') for i in range(5)]
        dups = []

        def fake_is_same_story(client, topic, recent):
            # T0 a T1 jsou duplicity (nejvirálnější témata už vyšla dřív)
            if topic['topic'] in ('T0', 'T1'):
                return (1, 'stejná novinka')
            return (None, '')

        with patch.object(topic_dedup, 'get_recent_published_topics', return_value=RECENT), \
             patch.object(topic_dedup, '_llm_is_same_story', fake_is_same_story), \
             patch('anthropic.Anthropic'):
            taken = list(islice(topic_dedup.iter_llm_unique_topics(topics, on_duplicate=dups.append), 2))

        assert [t['topic'] for t in taken] == ['T2', 'T3']
        assert [t['topic'] for t in dups] == ['T0', 'T1']
        assert all(t['_dedup_match']['match_type'] == 'llm' for t in dups)
        assert all(t['_dedup_match']['topic'] == 'Staré téma' for t in dups)

    def test_exhausting_checks_everything(self):
        """Když volající vybere vše, zkontroluje se každý kandidát."""
        topics = [_topic(f'T{i}') for i in range(4)]
        calls = []

        def fake_is_same_story(client, topic, recent):
            calls.append(topic['topic'])
            return (None, '')

        with patch.object(topic_dedup, 'get_recent_published_topics', return_value=RECENT), \
             patch.object(topic_dedup, '_llm_is_same_story', fake_is_same_story), \
             patch('anthropic.Anthropic'):
            taken = list(topic_dedup.iter_llm_unique_topics(topics))

        assert len(taken) == 4
        assert len(calls) == 4

    def test_no_recent_topics_skips_llm(self):
        """Bez publikované historie se LLM vůbec nevolá a kandidáti projdou v pořadí."""
        topics = [_topic(f'T{i}') for i in range(5)]
        with patch.object(topic_dedup, 'get_recent_published_topics', return_value=[]), \
             patch.object(topic_dedup, '_llm_is_same_story') as llm:
            taken = list(islice(topic_dedup.iter_llm_unique_topics(topics), 2))
        assert [t['topic'] for t in taken] == ['T0', 'T1']
        llm.assert_not_called()

"""
Testy pro topic_dedup — hlavně `needed` limit LLM druhé vrstvy
(fallback kandidáti: publikuj další v pořadí, když top témata jsou duplicitní).
"""

from unittest.mock import patch

import topic_dedup


def _topic(name):
    return {'topic': name, 'title': name, 'game_name': name}


RECENT = [{'topic': 'Staré téma', 'title': 'Staré téma', 'timestamp': '2026-07-09T08:00:00', 'game_name': ''}]


class TestLlmFilterNeededLimit:
    def test_stops_checking_once_needed_survivors_found(self):
        """Jakmile přežije `needed` témat, zbylí kandidáti se už LLM nekontrolují."""
        topics = [_topic(f'T{i}') for i in range(5)]
        calls = []

        def fake_is_same_story(client, topic, recent):
            calls.append(topic['topic'])
            return (None, '')  # nic není duplicita

        with patch.object(topic_dedup, 'get_recent_published_topics', return_value=RECENT), \
             patch.object(topic_dedup, '_llm_is_same_story', fake_is_same_story), \
             patch('anthropic.Anthropic'):
            unique, dups = topic_dedup.llm_filter_duplicate_topics(topics, needed=2)

        assert [t['topic'] for t in unique] == ['T0', 'T1']
        assert calls == ['T0', 'T1']  # T2–T4 se nekontrolovaly (ušetřená volání)
        assert dups == []

    def test_duplicates_dont_count_toward_needed(self):
        """Duplicitní top témata se přeskočí a limit naplní další kandidáti v pořadí."""
        topics = [_topic(f'T{i}') for i in range(5)]

        def fake_is_same_story(client, topic, recent):
            # T0 a T1 jsou duplicity (nejvirálnější témata už vyšla dřív)
            if topic['topic'] in ('T0', 'T1'):
                return (1, 'stejná novinka')
            return (None, '')

        with patch.object(topic_dedup, 'get_recent_published_topics', return_value=RECENT), \
             patch.object(topic_dedup, '_llm_is_same_story', fake_is_same_story), \
             patch('anthropic.Anthropic'):
            unique, dups = topic_dedup.llm_filter_duplicate_topics(topics, needed=2)

        assert [t['topic'] for t in unique] == ['T2', 'T3']
        assert [t['topic'] for t in dups] == ['T0', 'T1']
        assert all(t['_dedup_match']['match_type'] == 'llm' for t in dups)

    def test_no_needed_checks_everything(self):
        """Bez `needed` (manual_article aj.) se chová jako dřív — kontroluje vše."""
        topics = [_topic(f'T{i}') for i in range(4)]
        calls = []

        def fake_is_same_story(client, topic, recent):
            calls.append(topic['topic'])
            return (None, '')

        with patch.object(topic_dedup, 'get_recent_published_topics', return_value=RECENT), \
             patch.object(topic_dedup, '_llm_is_same_story', fake_is_same_story), \
             patch('anthropic.Anthropic'):
            unique, dups = topic_dedup.llm_filter_duplicate_topics(topics)

        assert len(unique) == 4
        assert len(calls) == 4

    def test_no_recent_topics_trims_to_needed(self):
        """Bez publikované historie se nic nevolá, ale limit `needed` platí i tak."""
        topics = [_topic(f'T{i}') for i in range(5)]
        with patch.object(topic_dedup, 'get_recent_published_topics', return_value=[]):
            unique, dups = topic_dedup.llm_filter_duplicate_topics(topics, needed=2)
        assert len(unique) == 2
        assert dups == []

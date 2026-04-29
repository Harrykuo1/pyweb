import { describe, expect, it } from 'vitest'

import { matchHaystack, parseQuery } from './searchQuery'

// Mirrors backend/tests/test_search_query.py — keep the case tables
// in lockstep. Any divergence between this file and the Python suite
// is a parser drift bug.

const t = (text, negate = false) => ({ text, negate })

describe('parseQuery', () => {
  describe('empty / whitespace', () => {
    it('returns no groups for empty string', () => {
      expect(parseQuery('')).toEqual([])
    })
    it('returns no groups for whitespace-only', () => {
      expect(parseQuery('   \t  ')).toEqual([])
    })
    it('returns no groups for null/undefined', () => {
      expect(parseQuery(null)).toEqual([])
      expect(parseQuery(undefined)).toEqual([])
    })
  })

  describe('implicit AND', () => {
    it('parses single word', () => {
      expect(parseQuery('react')).toEqual([[t('react')]])
    })
    it('parses two implicit-AND words', () => {
      expect(parseQuery('react vue')).toEqual([[t('react'), t('vue')]])
    })
    it('collapses multiple spaces', () => {
      expect(parseQuery('react   vue')).toEqual([[t('react'), t('vue')]])
    })
  })

  describe('OR (Google-style low precedence)', () => {
    it('splits into two groups', () => {
      expect(parseQuery('react OR vue')).toEqual([[t('react')], [t('vue')]])
    })
    it('AND binds tighter than OR', () => {
      expect(parseQuery('senior react OR vue junior')).toEqual([
        [t('senior'), t('react')],
        [t('vue'), t('junior')],
      ])
    })
    it('lowercase or is a normal term', () => {
      expect(parseQuery('react or vue')).toEqual([
        [t('react'), t('or'), t('vue')],
      ])
    })
    it('ignores leading OR', () => {
      expect(parseQuery('OR react')).toEqual([[t('react')]])
    })
    it('ignores trailing OR', () => {
      expect(parseQuery('react OR')).toEqual([[t('react')]])
    })
    it('collapses consecutive OR', () => {
      expect(parseQuery('react OR OR vue')).toEqual([[t('react')], [t('vue')]])
    })
  })

  describe('negation', () => {
    it('dash prefix negates', () => {
      expect(parseQuery('react -junior')).toEqual([
        [t('react'), t('junior', true)],
      ])
    })
    it('uppercase NOT negates following token', () => {
      expect(parseQuery('react NOT junior')).toEqual([
        [t('react'), t('junior', true)],
      ])
    })
    it('lowercase not is a normal term', () => {
      expect(parseQuery('react not junior')).toEqual([
        [t('react'), t('not'), t('junior')],
      ])
    })
    it('drops dash with no next token', () => {
      expect(parseQuery('react -')).toEqual([[t('react')]])
    })
    it('drops dash separated by whitespace', () => {
      expect(parseQuery('react - foo')).toEqual([[t('react'), t('foo')]])
    })
    it('keeps inner dash for double-dash', () => {
      expect(parseQuery('--foo')).toEqual([[t('-foo', true)]])
    })
    it('NOT alone is a no-op', () => {
      expect(parseQuery('NOT')).toEqual([])
    })
    it('trailing NOT is a no-op', () => {
      expect(parseQuery('react NOT')).toEqual([[t('react')]])
    })
    it('NOT before OR is reset', () => {
      expect(parseQuery('NOT OR foo')).toEqual([[t('foo')]])
    })
    it('-OR is a literal negated term, not a separator', () => {
      expect(parseQuery('react -OR vue')).toEqual([
        [t('react'), t('OR', true), t('vue')],
      ])
    })
  })

  describe('phrases', () => {
    it('preserves whitespace inside quotes', () => {
      expect(parseQuery('"team lead"')).toEqual([[t('team lead')]])
    })
    it('parses phrase alongside other terms', () => {
      expect(parseQuery('senior "team lead"')).toEqual([
        [t('senior'), t('team lead')],
      ])
    })
    it('negated phrase via dash prefix', () => {
      expect(parseQuery('-"team lead"')).toEqual([[t('team lead', true)]])
    })
    it('negated phrase via NOT keyword', () => {
      expect(parseQuery('NOT "team lead"')).toEqual([[t('team lead', true)]])
    })
    it('drops empty quotes', () => {
      expect(parseQuery('react "" vue')).toEqual([[t('react'), t('vue')]])
    })
    it('treats OR inside quotes as literal', () => {
      expect(parseQuery('"react OR vue"')).toEqual([[t('react OR vue')]])
    })
    it('treats dash inside quotes as literal', () => {
      expect(parseQuery('"-junior"')).toEqual([[t('-junior')]])
    })
    it('handles unterminated quote by reading to end', () => {
      expect(parseQuery('react "team lead')).toEqual([
        [t('react'), t('team lead')],
      ])
    })
  })

  describe('combined', () => {
    it('matches the realistic example from spec', () => {
      // `senior react OR vue -junior "team lead"` (Google-style):
      // (senior AND react) OR (vue AND NOT junior AND "team lead")
      expect(parseQuery('senior react OR vue -junior "team lead"')).toEqual([
        [t('senior'), t('react')],
        [t('vue'), t('junior', true), t('team lead')],
      ])
    })
    it('NOT keyword in both groups', () => {
      expect(parseQuery('react NOT junior OR vue NOT senior')).toEqual([
        [t('react'), t('junior', true)],
        [t('vue'), t('senior', true)],
      ])
    })
  })
})

describe('matchHaystack', () => {
  it('returns true when parsed is empty (no filter)', () => {
    expect(matchHaystack([], 'anything')).toBe(true)
    expect(matchHaystack(parseQuery(''), 'anything')).toBe(true)
  })

  it('case-insensitive substring match', () => {
    const p = parseQuery('REACT')
    expect(matchHaystack(p, 'I love React Native')).toBe(true)
    expect(matchHaystack(p, 'vue only')).toBe(false)
  })

  it('AND requires all terms', () => {
    const p = parseQuery('senior react')
    expect(matchHaystack(p, 'senior react developer')).toBe(true)
    expect(matchHaystack(p, 'senior backend')).toBe(false)
    expect(matchHaystack(p, 'junior react')).toBe(false)
  })

  it('OR matches if any group matches', () => {
    const p = parseQuery('react OR vue')
    expect(matchHaystack(p, 'react app')).toBe(true)
    expect(matchHaystack(p, 'vue app')).toBe(true)
    expect(matchHaystack(p, 'angular app')).toBe(false)
  })

  it('negation excludes matching haystacks', () => {
    const p = parseQuery('react -junior')
    expect(matchHaystack(p, 'senior react developer')).toBe(true)
    expect(matchHaystack(p, 'junior react developer')).toBe(false)
  })

  it('phrase requires contiguous match', () => {
    const p = parseQuery('"team lead"')
    expect(matchHaystack(p, 'promoted to team lead in 2024')).toBe(true)
    expect(matchHaystack(p, 'led the team')).toBe(false)
  })

  it('combined boolean query end-to-end', () => {
    // Same example as the parse test, evaluated against haystacks.
    const p = parseQuery('senior react OR vue -junior "team lead"')
    expect(matchHaystack(p, 'senior react work')).toBe(true) // group 1
    expect(matchHaystack(p, 'vue dev, team lead, no juniors here')).toBe(false) // group 2 excluded by 'junior' substring
    expect(matchHaystack(p, 'vue dev, team lead in 2024')).toBe(true) // group 2
    expect(matchHaystack(p, 'go backend')).toBe(false)
  })

  it('handles null / undefined haystack as empty string', () => {
    const p = parseQuery('react')
    expect(matchHaystack(p, null)).toBe(false)
    expect(matchHaystack(p, undefined)).toBe(false)
  })
})

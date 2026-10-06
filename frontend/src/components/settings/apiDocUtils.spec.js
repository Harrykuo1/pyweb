import { describe, expect, it } from 'vitest'
import {
  operations,
  referencedSchemas,
  resolveSchema,
  schemaType,
} from './apiDocUtils'
describe('OpenAPI reference rendering', () => {
  it('only enumerates operations and carries path-level parameters', () => {
    const spec = {
      paths: {
        '/api/a': {
          summary: 'not a method',
          parameters: [{ name: 'id' }],
          get: { parameters: [{ name: 'q' }] },
          post: {},
        },
      },
    }
    const ops = operations(spec)
    expect(ops.map((o) => o.key)).toEqual(['GET /api/a', 'POST /api/a'])
    expect(ops[0].parameters.map((p) => p.name)).toEqual(['id', 'q'])
  })
  it('resolves nested references without infinite recursion', () => {
    const ref = { $ref: '#/components/schemas/Node' }
    const schema = {
      type: 'object',
      properties: { children: { type: 'array', items: ref } },
    }
    const spec = { components: { schemas: { Node: schema } } }
    expect(referencedSchemas(ref, spec)).toEqual({ Node: schema })
    expect(resolveSchema(ref, spec)).toBe(schema)
    expect(schemaType(schema.properties.children)).toBe('Node[]')
    expect(schemaType({ anyOf: [{ type: 'string' }, { type: 'null' }] })).toBe(
      'string | null',
    )
  })
})

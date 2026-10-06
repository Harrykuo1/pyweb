const METHODS = new Set([
  'get',
  'post',
  'put',
  'patch',
  'delete',
  'head',
  'options',
])

export function operations(spec) {
  return Object.entries(spec?.paths || {}).flatMap(([path, item]) =>
    Object.entries(item)
      .filter(([method]) => METHODS.has(method))
      .map(([method, operation]) => ({
        ...operation,
        method: method.toUpperCase(),
        path,
        key: `${method.toUpperCase()} ${path}`,
        parameters: [
          ...(item.parameters || []),
          ...(operation.parameters || []),
        ],
      })),
  )
}

export function resolveSchema(schema, spec) {
  if (!schema?.$ref) return schema || {}
  const name = schema.$ref.split('/').at(-1)
  return spec.components?.schemas?.[name] || schema
}

export function schemaType(schema) {
  if (!schema) return '—'
  if (schema.$ref) return schema.$ref.split('/').at(-1)
  if (schema.anyOf || schema.oneOf)
    return (schema.anyOf || schema.oneOf).map(schemaType).join(' | ')
  if (schema.type === 'array') return `${schemaType(schema.items)}[]`
  return schema.format
    ? `${schema.type} (${schema.format})`
    : schema.type || 'object'
}

export function referencedSchemas(operation, spec) {
  const found = {}
  function visit(value) {
    if (!value || typeof value !== 'object') return
    if (value.$ref?.startsWith('#/components/schemas/')) {
      const name = value.$ref.split('/').at(-1)
      if (!(name in found) && spec.components?.schemas?.[name]) {
        found[name] = spec.components.schemas[name]
        visit(found[name])
      }
    }
    Object.values(value).forEach(visit)
  }
  visit(operation)
  return found
}

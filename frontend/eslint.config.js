import js from '@eslint/js'
import pluginVue from 'eslint-plugin-vue'
import prettier from 'eslint-config-prettier'
import globals from 'globals'

// ESLint flat config. Vue's "essential" tier catches real errors (parse
// bugs, wrong reactivity, missing :key) without imposing stylistic rules —
// formatting is Prettier's job, and eslint-config-prettier (kept last)
// disables any ESLint rules that would fight it.
export default [
  { ignores: ['dist/**', 'coverage/**'] },
  js.configs.recommended,
  ...pluginVue.configs['flat/essential'],
  {
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      // Allow intentionally-unused identifiers when prefixed with _, and
      // don't force consuming the binding of a catch (err) clause.
      'no-unused-vars': [
        'error',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          caughtErrors: 'none',
          // `const { drop, ...rest } = obj` to omit a key is intentional.
          ignoreRestSiblings: true,
        },
      ],
      // App-level views and the navbar are legitimately single-word
      // (Home, Login, Navbar); this rule is aimed at shared libraries.
      'vue/multi-word-component-names': 'off',
    },
  },
  prettier,
]

<script setup>
import { computed, ref } from 'vue'
import { ElIcon, ElInput, ElOption, ElSelect } from 'element-plus'
import {
  Calendar,
  OfficeBuilding,
  Operation,
  Search,
} from '@element-plus/icons-vue'

import { jobsApi } from '../../api/jobs'
import {
  CATEGORY_FILTER_LIMIT,
  COMPANY_FILTER_LIMIT,
  KIND_FILTER_OPTIONS,
  YEAR_OPTIONS,
} from './jobFilters'

// Each filter is an independent two-way binding back to the URL-synced
// state in Jobs.vue.
const kind = defineModel('kind', { type: String, default: '' })
const year = defineModel('year', { default: null })
const company = defineModel('company', { type: Array, default: () => [] })
const category = defineModel('category', { type: Array, default: () => [] })
const q = defineModel('q', { type: String, default: '' })

// el-select with `remote` calls these on every keystroke. The dropdown
// shows only what the API returned for the current keyword — chips already
// selected render straight from their string value, so we don't inject
// them into options (that would surface unrelated chips during a fresh
// keyword search).
const companySuggestions = ref([])
const categorySuggestions = ref([])

async function fetchCompanySuggestions(queryString) {
  try {
    companySuggestions.value = await jobsApi.listCompanies(
      queryString || undefined,
    )
  } catch {
    companySuggestions.value = []
  }
}

async function fetchCategorySuggestions(queryString) {
  try {
    categorySuggestions.value = await jobsApi.listCategories(
      queryString || undefined,
    )
  } catch {
    categorySuggestions.value = []
  }
}

// Block auto-repeat Backspace when the inline editor is empty so a held
// key can't rapid-fire delete every selected chip. The first press still
// removes one chip; the user has to release and press again for the next.
function onChipFilterKeydown(event) {
  if (
    event.key === 'Backspace' &&
    event.repeat &&
    event.target instanceof HTMLInputElement &&
    event.target.value === ''
  ) {
    event.preventDefault()
    event.stopPropagation()
  }
}

// Push already-selected matches to the bottom so the user always sees new
// options first; each group keeps the API's alphabetical order.
function reorderSuggestions(selected, suggestions) {
  const sel = new Set(selected)
  const fresh = []
  const stale = []
  for (const item of suggestions) {
    if (sel.has(item)) stale.push(item)
    else fresh.push(item)
  }
  return [...fresh, ...stale]
}

const displayedCompanySuggestions = computed(() =>
  reorderSuggestions(company.value, companySuggestions.value),
)
const displayedCategorySuggestions = computed(() =>
  reorderSuggestions(category.value, categorySuggestions.value),
)
</script>

<template>
  <div class="filter-bar">
    <div class="filter-row filter-row--meta">
      <div class="kind-chips" role="tablist" aria-label="類型篩選">
        <button
          v-for="opt in KIND_FILTER_OPTIONS"
          :key="opt.value || 'all'"
          type="button"
          role="tab"
          :aria-selected="kind === opt.value"
          :class="[
            'kind-chip',
            `kind-chip--${opt.value || 'all'}`,
            { 'is-active': kind === opt.value },
          ]"
          :data-test="`filter-kind-${opt.value || 'all'}`"
          @click="kind = opt.value"
        >
          {{ opt.label }}
        </button>
      </div>

      <el-select
        v-model="year"
        placeholder="年份"
        clearable
        data-test="filter-year"
        class="filter-year"
      >
        <template #prefix>
          <el-icon><Calendar /></el-icon>
        </template>
        <el-option
          v-for="y in YEAR_OPTIONS"
          :key="y"
          :label="`${y} 年`"
          :value="y"
        />
      </el-select>

      <el-select
        v-model="company"
        multiple
        filterable
        remote
        :remote-method="fetchCompanySuggestions"
        :reserve-keyword="false"
        :multiple-limit="COMPANY_FILTER_LIMIT"
        placeholder="公司（可多選）"
        clearable
        data-test="filter-company"
        class="filter-company"
        @keydown.capture="onChipFilterKeydown"
      >
        <template #prefix>
          <el-icon><OfficeBuilding /></el-icon>
        </template>
        <el-option
          v-for="c in displayedCompanySuggestions"
          :key="c"
          :label="c"
          :value="c"
        />
      </el-select>

      <el-select
        v-model="category"
        multiple
        filterable
        remote
        :remote-method="fetchCategorySuggestions"
        :reserve-keyword="false"
        :multiple-limit="CATEGORY_FILTER_LIMIT"
        placeholder="職類（可多選）"
        clearable
        data-test="filter-category"
        class="filter-category"
        @keydown.capture="onChipFilterKeydown"
      >
        <template #prefix>
          <el-icon><Operation /></el-icon>
        </template>
        <el-option
          v-for="c in displayedCategorySuggestions"
          :key="c"
          :label="c"
          :value="c"
        />
      </el-select>
    </div>

    <el-input
      v-model="q"
      placeholder="搜尋姓名、心得內文"
      :prefix-icon="Search"
      clearable
      data-test="filter-search"
      class="filter-search"
    />
  </div>
</template>

<style scoped>
.filter-bar {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  background: var(--surface-0);
  border: 1px solid rgba(15, 23, 42, 0.06);
  border-radius: var(--radius-lg);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04);
}

/* Row 1 — narrow widgets (kind chips, year, company autocomplete) so
   the row stays compact and the search input can take a full-width
   line of its own below. */
.filter-row {
  display: flex;
  align-items: center;
  gap: var(--sp-sm);
  flex-wrap: wrap;
}

/* ----- Kind segmented chips ----- */
.kind-chips {
  display: inline-flex;
  background: var(--surface-2, #f1f5f9);
  border-radius: 999px;
  padding: 3px;
  gap: 2px;
}

.kind-chip {
  border: 0;
  background: transparent;
  padding: 5px 14px;
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-500);
  border-radius: 999px;
  cursor: pointer;
  transition:
    background-color var(--dur) var(--ease),
    color var(--dur) var(--ease),
    box-shadow var(--dur) var(--ease);
}

.kind-chip:hover {
  color: var(--ink-700);
}

.kind-chip.is-active {
  background: var(--surface-0);
  color: var(--ink-900);
  box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
}

.kind-chip--internship.is-active {
  color: var(--kind-internship-ink);
}

.kind-chip--fulltime.is-active {
  color: var(--kind-fulltime-ink);
}

.filter-year {
  width: 130px;
}

/* Company is given roughly twice the horizontal real-estate of category
   on desktop because company names tend to be longer (and there are
   typically more of them in the dropdown). flex-wrap on the parent row
   handles the narrow-viewport stack automatically once the combined
   widths exceed the row. */
.filter-company {
  flex: 2;
  min-width: 200px;
}

.filter-category {
  flex: 1;
  min-width: 160px;
}

/* Suppress the nested border that would otherwise appear around the
   chips' inline editor — el-select renders an internal input wrapper
   when filterable+multiple, and our generic .filter-bar input shadow
   leaks into it. We want only the outer wrapper to show a border. */
.filter-company :deep(.el-select__input),
.filter-company :deep(.el-select__selection) input,
.filter-category :deep(.el-select__input),
.filter-category :deep(.el-select__selection) input {
  box-shadow: none !important;
  border: none !important;
  outline: none !important;
}

/* Row 2 — search takes the full width of the filter bar so users can
   read most of what they're typing without truncation. */
.filter-search {
  width: 100%;
}

/* Element Plus inputs all share these radii / shadows so the filter
   bar reads as one cohesive surface instead of a row of mismatched
   widgets. */
.filter-bar :deep(.el-input__wrapper),
.filter-bar :deep(.el-select__wrapper) {
  border-radius: var(--radius-md);
  box-shadow: 0 0 0 1px rgba(15, 23, 42, 0.06) inset;
  transition: box-shadow var(--dur) var(--ease);
}

.filter-bar :deep(.el-input__wrapper):hover,
.filter-bar :deep(.el-select__wrapper):hover {
  box-shadow: 0 0 0 1px rgba(99, 102, 241, 0.35) inset;
}

.filter-bar :deep(.el-input__wrapper.is-focus),
.filter-bar :deep(.el-select__wrapper.is-focused) {
  box-shadow: 0 0 0 1.5px var(--brand-primary) inset;
}

@media (max-width: 640px) {
  .filter-bar {
    padding: 8px;
  }

  .filter-row {
    /* Each control on phones gets its own line so the labels and clear
       buttons aren't cramped against each other. */
    flex-direction: column;
    align-items: stretch;
  }

  .filter-year,
  .filter-company,
  .filter-category {
    width: 100%;
  }
}
</style>

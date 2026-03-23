<template>
  <div class="bv">

    <!-- ── Header ── -->
    <header class="bv-header">
      <div class="bv-header__brand">
        <span class="bv-header__icon">⚽</span>
        <span class="bv-header__name">SAI Tipster</span>
        <span class="bv-header__powered">powered by MiroFish AI</span>
      </div>
      <nav class="bv-nav">
        <button
          v-for="tab in tabs" :key="tab.key"
          :class="['bv-nav__item', { active: activeTab === tab.key }]"
          @click="activeTab = tab.key"
        >{{ tab.label }}</button>
      </nav>
    </header>

    <!-- ── FIXTURES ── -->
    <main v-if="activeTab === 'fixtures'" class="bv-main">
      <div class="bv-toolbar">
        <div class="bv-chips">
          <button
            v-for="c in compFilters" :key="c.code"
            :class="['bv-chip', { active: compFilter === c.code }]"
            @click="compFilter = c.code"
          >{{ c.label }}</button>
        </div>
        <button class="bv-btn bv-btn--ghost" @click="loadFixtures">↺ Refresh</button>
      </div>

      <div v-if="loadingFixtures" class="bv-state bv-state--loading">
        <div class="bv-spinner"></div> Loading fixtures…
      </div>
      <div v-else-if="fixturesError" class="bv-state bv-state--error">{{ fixturesError }}</div>
      <div v-else-if="!filteredFixtures.length" class="bv-state">No upcoming fixtures.</div>

      <div v-else class="bv-fixture-grid">
        <div
          v-for="f in filteredFixtures" :key="f.fixture_id"
          :class="['bv-fixture', { 'bv-fixture--predicted': hasPrediction(f.fixture_id) }]"
          @click="openFixture(f)"
        >
          <div class="bv-fixture__top">
            <span :class="['bv-badge', f.competition_code.toLowerCase()]">
              {{ f.competition_code === 'SA' ? '🇮🇹 Serie A' : '⭐ UCL' }}
            </span>
            <span class="bv-fixture__date">{{ fmtDate(f.match_date) }}</span>
            <span v-if="f.matchday" class="bv-fixture__md">MD {{ f.matchday }}</span>
            <span v-else-if="f.stage" class="bv-fixture__md">{{ f.stage }}</span>
          </div>
          <div class="bv-fixture__teams">
            <span class="bv-fixture__team">{{ f.home_team }}</span>
            <span class="bv-fixture__vs">vs</span>
            <span class="bv-fixture__team">{{ f.away_team }}</span>
          </div>

          <!-- Quick odds strip (if available) -->
          <div v-if="getQuickOdds(f.fixture_id)" class="bv-fixture__odds">
            <span class="bv-odd bv-odd--h">{{ getQuickOdds(f.fixture_id).home }}</span>
            <span class="bv-odd bv-odd--d">{{ getQuickOdds(f.fixture_id).draw }}</span>
            <span class="bv-odd bv-odd--a">{{ getQuickOdds(f.fixture_id).away }}</span>
          </div>

          <div class="bv-fixture__footer">
            <span v-if="hasPrediction(f.fixture_id)" class="bv-badge bv-badge--green">✓ Predicted</span>
            <span v-if="isRunning(f.fixture_id)" class="bv-badge bv-badge--yellow">
              <span class="bv-spinner bv-spinner--xs"></span> Running…
            </span>
          </div>
        </div>
      </div>
    </main>

    <!-- ── FIXTURE DETAIL (slide-in panel) ── -->
    <div v-if="activeFixture" class="bv-panel-overlay" @click.self="activeFixture = null">
      <aside class="bv-panel">
        <button class="bv-panel__close" @click="activeFixture = null">✕</button>

        <div class="bv-panel__header">
          <span :class="['bv-badge', activeFixture.competition_code.toLowerCase()]">
            {{ activeFixture.competition }}
          </span>
          <h2>{{ activeFixture.home_team }} <span class="dim">vs</span> {{ activeFixture.away_team }}</h2>
          <p class="bv-panel__date">{{ fmtDate(activeFixture.match_date) }}</p>
        </div>

        <!-- LIVE ODDS -->
        <section class="bv-section">
          <h3 class="bv-section__title">📈 Live Odds
            <span v-if="loadingOdds" class="bv-spinner bv-spinner--xs"></span>
            <span v-if="!oddsApiConfigured" class="bv-warning-badge">No ODDS_API_KEY set</span>
          </h3>
          <div v-if="activeOdds && !activeOdds.error" class="bv-odds-table">
            <!-- Consensus best odds -->
            <div class="bv-odds-row bv-odds-row--consensus">
              <span class="bv-odds-row__book">Best odds</span>
              <span class="bv-odds-cell bv-odds-cell--h">
                {{ activeFixture.home_team.split(' ').pop() }}<br>
                <strong>{{ activeOdds.consensus?.home || '—' }}</strong>
              </span>
              <span class="bv-odds-cell bv-odds-cell--d">
                Draw<br><strong>{{ activeOdds.consensus?.draw || '—' }}</strong>
              </span>
              <span class="bv-odds-cell bv-odds-cell--a">
                {{ activeFixture.away_team.split(' ').pop() }}<br>
                <strong>{{ activeOdds.consensus?.away || '—' }}</strong>
              </span>
              <span class="bv-odds-cell">O2.5<br><strong>{{ activeOdds.consensus?.over_2_5 || '—' }}</strong></span>
              <span class="bv-odds-cell">U2.5<br><strong>{{ activeOdds.consensus?.under_2_5 || '—' }}</strong></span>
              <span v-if="activeOdds.consensus?.btts_yes" class="bv-odds-cell">
                BTTS Y<br><strong>{{ activeOdds.consensus.btts_yes }}</strong>
              </span>
            </div>
            <!-- Per-bookmaker -->
            <div
              v-for="(book_odds, book) in activeOdds.bookmakers"
              :key="book"
              class="bv-odds-row"
            >
              <span class="bv-odds-row__book">{{ book }}</span>
              <span class="bv-odds-cell">{{ book_odds.home || '—' }}</span>
              <span class="bv-odds-cell">{{ book_odds.draw || '—' }}</span>
              <span class="bv-odds-cell">{{ book_odds.away || '—' }}</span>
              <span class="bv-odds-cell">{{ book_odds.over_2_5 || '—' }}</span>
              <span class="bv-odds-cell">{{ book_odds.under_2_5 || '—' }}</span>
              <span class="bv-odds-cell">{{ book_odds.btts_yes || '—' }}</span>
            </div>
          </div>
          <div v-else-if="activeOdds?.error" class="bv-state--warn">{{ activeOdds.error }}</div>
          <div v-else-if="!loadingOdds" class="bv-state dim">No odds data available.</div>
        </section>

        <!-- AI PREDICTION -->
        <section class="bv-section">
          <h3 class="bv-section__title">🤖 AI Prediction</h3>
          <div v-if="activePrediction" class="bv-pred-summary">
            <!-- 1X2 -->
            <div class="bv-market">
              <div class="bv-market__lbl">Match Result</div>
              <div class="bv-bar-row">
                <div class="bv-bar-item">
                  <span>Home</span>
                  <div class="bv-bar-track"><div class="bv-bar-fill --win" :style="{width: activePrediction.home_win_pct+'%'}"></div></div>
                  <span>{{ activePrediction.home_win_pct }}%</span>
                </div>
                <div class="bv-bar-item">
                  <span>Draw</span>
                  <div class="bv-bar-track"><div class="bv-bar-fill --draw" :style="{width: activePrediction.draw_pct+'%'}"></div></div>
                  <span>{{ activePrediction.draw_pct }}%</span>
                </div>
                <div class="bv-bar-item">
                  <span>Away</span>
                  <div class="bv-bar-track"><div class="bv-bar-fill --win" :style="{width: activePrediction.away_win_pct+'%'}"></div></div>
                  <span>{{ activePrediction.away_win_pct }}%</span>
                </div>
              </div>
            </div>
            <!-- Market pills grid -->
            <div class="bv-markets-grid">
              <div class="bv-market-mini" v-for="m in marketPills(activePrediction)" :key="m.label">
                <div class="bv-market-mini__lbl">{{ m.label }}</div>
                <div class="bv-pill-row">
                  <span :class="['bv-pill', m.overClass]">{{ m.overLabel }}<br><strong>{{ m.overPct }}%</strong></span>
                  <span :class="['bv-pill', m.underClass]">{{ m.underLabel }}<br><strong>{{ m.underPct }}%</strong></span>
                </div>
              </div>
            </div>
            <!-- Scoreline -->
            <div v-if="activePrediction.most_likely_scoreline" class="bv-scoreline">
              <span class="dim">Most likely scoreline:</span>
              <span class="bv-scoreline__val">{{ activePrediction.most_likely_scoreline }}</span>
              <span :class="['bv-confidence', activePrediction.confidence]">{{ activePrediction.confidence }}</span>
            </div>
          </div>
          <div v-else class="bv-predict-cta">
            <p class="dim">No prediction yet for this match.</p>
            <button
              class="bv-btn bv-btn--primary bv-btn--lg"
              :disabled="isRunning(activeFixture.fixture_id)"
              @click="runPrediction(activeFixture)"
            >
              <span v-if="isRunning(activeFixture.fixture_id)">
                <span class="bv-spinner bv-spinner--xs"></span> Simulating… (~3 min)
              </span>
              <span v-else>🤖 Run AI Prediction</span>
            </button>
          </div>
        </section>

        <!-- NEWS FEED -->
        <section class="bv-section">
          <h3 class="bv-section__title">📰 News & Injuries
            <span v-if="loadingNews" class="bv-spinner bv-spinner--xs"></span>
          </h3>
          <div v-if="activeNews.length" class="bv-news-list">
            <a
              v-for="(article, i) in activeNews"
              :key="i"
              :href="article.url"
              target="_blank"
              class="bv-news-item"
              :class="{ 'bv-news-item--injury': article.is_injury_report }"
            >
              <div class="bv-news-item__source">
                <span :class="['bv-source-badge', sourceClass(article.source)]">{{ article.source }}</span>
                <span class="bv-news-item__date">{{ fmtNewsDate(article.published_at) }}</span>
              </div>
              <div class="bv-news-item__title">{{ article.title }}</div>
              <div v-if="article.summary" class="bv-news-item__summary">{{ article.summary }}</div>
            </a>
          </div>
          <div v-else-if="!loadingNews" class="bv-state dim">No news articles found.</div>
        </section>

      </aside>
    </div>

    <!-- ── PREDICTIONS TAB ── -->
    <main v-if="activeTab === 'predictions'" class="bv-main">
      <div v-if="!predictions.length" class="bv-state">
        No predictions yet. Open a fixture and click "Run AI Prediction".
      </div>
      <div v-else class="bv-pred-list">
        <div v-for="pred in predictions" :key="pred.fixture_id" class="bv-pred-card">
          <div class="bv-pred-card__header">
            <div>
              <span :class="['bv-badge', compClass(pred.competition)]">{{ pred.competition }}</span>
              <h3>{{ pred.match_label }}</h3>
              <span class="dim bv-pred-card__date">{{ fmtDate(pred.created_at) }}</span>
            </div>
            <span :class="['bv-confidence', pred.confidence]">{{ pred.confidence }}</span>
          </div>
          <!-- 1X2 summary -->
          <div class="bv-pred-card__result">
            <div class="bv-result-pill" :class="resultClass(pred)">
              <span>{{ resultLabel(pred) }}</span>
              <strong>{{ resultPct(pred) }}%</strong>
            </div>
          </div>
          <!-- All markets mini -->
          <div class="bv-markets-grid bv-markets-grid--compact">
            <div class="bv-market-mini" v-for="m in marketPills(pred)" :key="m.label">
              <div class="bv-market-mini__lbl">{{ m.label }}</div>
              <div class="bv-pill-row">
                <span :class="['bv-pill', m.overClass]">{{ m.overLabel }} {{ m.overPct }}%</span>
                <span :class="['bv-pill', m.underClass]">{{ m.underLabel }} {{ m.underPct }}%</span>
              </div>
            </div>
          </div>
          <div v-if="pred.most_likely_scoreline" class="bv-scoreline">
            <span class="dim">Scoreline:</span>
            <span class="bv-scoreline__val">{{ pred.most_likely_scoreline }}</span>
          </div>
          <!-- Live odds alongside -->
          <div v-if="pred.live_odds?.consensus" class="bv-pred-card__odds">
            <span class="dim">Live odds:</span>
            <span class="bv-odd bv-odd--h">{{ pred.live_odds.consensus.home }}</span>
            <span class="bv-odd bv-odd--d">{{ pred.live_odds.consensus.draw }}</span>
            <span class="bv-odd bv-odd--a">{{ pred.live_odds.consensus.away }}</span>
          </div>
        </div>
      </div>
    </main>

    <!-- ── STANDINGS TAB ── -->
    <main v-if="activeTab === 'standings'" class="bv-main">
      <div class="bv-chips">
        <button
          v-for="c in compFilters.filter(x => x.code !== 'ALL')" :key="c.code"
          :class="['bv-chip', { active: standingsComp === c.code }]"
          @click="loadStandings(c.code)"
        >{{ c.label }}</button>
      </div>
      <div v-if="loadingStandings" class="bv-state bv-state--loading">
        <div class="bv-spinner"></div> Loading…
      </div>
      <table v-else-if="standings.length" class="bv-table">
        <thead>
          <tr><th>#</th><th>Club</th><th>P</th><th>W</th><th>D</th><th>L</th>
              <th>GF</th><th>GA</th><th>GD</th><th>Pts</th><th>Form</th></tr>
        </thead>
        <tbody>
          <tr v-for="r in standings" :key="r.position">
            <td>{{ r.position }}</td>
            <td class="bv-table__club">{{ r.team_name }}</td>
            <td>{{ r.played }}</td><td>{{ r.won }}</td><td>{{ r.drawn }}</td><td>{{ r.lost }}</td>
            <td>{{ r.goals_for }}</td><td>{{ r.goals_against }}</td>
            <td :class="r.goal_difference > 0 ? 'pos' : r.goal_difference < 0 ? 'neg' : ''">
              {{ r.goal_difference > 0 ? '+' : '' }}{{ r.goal_difference }}
            </td>
            <td class="pts">{{ r.points }}</td>
            <td class="bv-form-row">
              <span
                v-for="(ch, i) in (r.form || '').split(',').filter(Boolean)"
                :key="i"
                :class="['bv-dot', ch.trim()]"
              >{{ ch.trim() }}</span>
            </td>
          </tr>
        </tbody>
      </table>
    </main>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'

// ── Config ─────────────────────────────────────────────────────────────────
const API = import.meta.env.VITE_API_URL || 'http://localhost:5050/api'

// ── Tabs ───────────────────────────────────────────────────────────────────
const activeTab = ref('fixtures')
const tabs = [
  { key: 'fixtures',    label: '📅 Fixtures' },
  { key: 'predictions', label: '🤖 Predictions' },
  { key: 'standings',   label: '📊 Standings' },
]
const compFilters = [
  { code: 'ALL', label: 'All' },
  { code: 'SA',  label: '🇮🇹 Serie A' },
  { code: 'CL',  label: '⭐ UCL' },
]
const compFilter = ref('ALL')

// ── Fixtures ───────────────────────────────────────────────────────────────
const fixtures = ref([])
const loadingFixtures = ref(false)
const fixturesError = ref(null)
const filteredFixtures = computed(() =>
  compFilter.value === 'ALL' ? fixtures.value
    : fixtures.value.filter(f => f.competition_code === compFilter.value)
)

// ── Predictions ────────────────────────────────────────────────────────────
const predictions = ref([])
const predMap = ref({})
const runningIds = ref(new Set())

// ── Active fixture panel ───────────────────────────────────────────────────
const activeFixture = ref(null)
const activeOdds = ref(null)
const loadingOdds = ref(false)
const activeNews = ref([])
const loadingNews = ref(false)
const oddsApiConfigured = ref(true)
const quickOddsMap = ref({})

// ── Standings ──────────────────────────────────────────────────────────────
const standings = ref([])
const loadingStandings = ref(false)
const standingsComp = ref('SA')

// ── Computed ───────────────────────────────────────────────────────────────
const activePrediction = computed(() =>
  activeFixture.value ? predMap.value[activeFixture.value.fixture_id] ?? null : null
)

// ── Data loading ───────────────────────────────────────────────────────────
async function loadFixtures() {
  loadingFixtures.value = true
  fixturesError.value = null
  try {
    const res = await fetch(`${API}/fixtures`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    const data = await res.json()
    if (data.error) throw new Error(data.error)
    fixtures.value = data
    // Load odds for all in background
    loadAllOdds()
  } catch (e) {
    fixturesError.value = `Could not load fixtures: ${e.message}`
  } finally {
    loadingFixtures.value = false
  }
}

async function loadAllOdds() {
  for (const code of ['SA', 'CL']) {
    try {
      const res = await fetch(`${API}/odds/${code}`)
      if (!res.ok) { oddsApiConfigured.value = false; continue }
      const data = await res.json()
      if (data.error) { oddsApiConfigured.value = false; continue }
      for (const event of (data || [])) {
        // Match to our fixture
        const fixture = fixtures.value.find(f =>
          namesMatch(f.home_team, event.home_team) &&
          namesMatch(f.away_team, event.away_team)
        )
        if (fixture && event.consensus) {
          quickOddsMap.value[fixture.fixture_id] = event.consensus
        }
      }
    } catch { oddsApiConfigured.value = false }
  }
}

async function loadPredictions() {
  try {
    const res = await fetch(`${API}/predictions`)
    if (!res.ok) return
    const data = await res.json()
    predictions.value = data
    predMap.value = {}
    data.forEach(p => { predMap.value[p.fixture_id] = p })
  } catch {}
}

async function loadStandings(code) {
  standingsComp.value = code
  loadingStandings.value = true
  standings.value = []
  try {
    const res = await fetch(`${API}/standings/${code}`)
    if (!res.ok) throw new Error()
    standings.value = await res.json()
  } catch {} finally {
    loadingStandings.value = false
  }
}

// ── Fixture panel ──────────────────────────────────────────────────────────
async function openFixture(fixture) {
  activeFixture.value = fixture
  activeOdds.value = null
  activeNews.value = []

  // Load odds
  if (oddsApiConfigured.value) {
    loadingOdds.value = true
    try {
      const res = await fetch(`${API}/odds/fixture/${fixture.fixture_id}`)
      const data = await res.json()
      activeOdds.value = data.error ? null : data
      if (data.error && data.error.includes('ODDS_API_KEY')) oddsApiConfigured.value = false
    } catch {} finally { loadingOdds.value = false }
  }

  // Load news
  loadingNews.value = true
  try {
    const comp = encodeURIComponent(fixture.competition)
    const res = await fetch(
      `${API}/news/${encodeURIComponent(fixture.home_team)}/${encodeURIComponent(fixture.away_team)}?competition=${comp}`
    )
    if (res.ok) activeNews.value = await res.json()
  } catch {} finally { loadingNews.value = false }
}

// ── Prediction ─────────────────────────────────────────────────────────────
async function runPrediction(fixture) {
  const id = fixture.fixture_id
  runningIds.value = new Set([...runningIds.value, id])
  try {
    const res = await fetch(`${API}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fixture_id: id }),
    })
    if (!res.ok) {
      const e = await res.json()
      throw new Error(e.error || `HTTP ${res.status}`)
    }
    const pred = await res.json()
    pred.fixture_id = id
    pred.match_label = `${fixture.home_team} vs ${fixture.away_team}`
    pred.competition = fixture.competition
    pred.created_at = new Date().toISOString()
    predMap.value[id] = pred
    predictions.value = [pred, ...predictions.value.filter(p => p.fixture_id !== id)]
  } catch (e) {
    alert(`Prediction failed: ${e.message}`)
  } finally {
    const s = new Set(runningIds.value); s.delete(id); runningIds.value = s
  }
}

// ── Helpers ────────────────────────────────────────────────────────────────
function hasPrediction(id) { return !!predMap.value[id] }
function isRunning(id) { return runningIds.value.has(id) }
function getQuickOdds(id) { return quickOddsMap.value[id] ?? null }

function namesMatch(a, b) {
  const kw = s => s.toLowerCase().replace(/[^a-z0-9]/g, ' ').split(' ').filter(w => w.length > 2)
  const ka = new Set(kw(a)), kb = new Set(kw(b))
  return [...ka].some(w => kb.has(w))
}

function fmtDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-GB', {
    weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit'
  })
}

function fmtNewsDate(iso) {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
}

function compClass(comp) {
  if (!comp) return ''
  return comp.toLowerCase().includes('serie') ? 'sa' : 'cl'
}

function sourceClass(source) {
  if (!source) return ''
  const s = source.toLowerCase()
  if (s.includes('bbc')) return 'bbc'
  if (s.includes('live')) return 'livescore'
  return 'default'
}

function marketPills(pred) {
  return [
    { label: 'Goals O/U 2.5', overLabel: 'Over', underLabel: 'Under',
      overPct: pred.over_2_5_pct, underPct: pred.under_2_5_pct,
      overClass: pred.over_2_5_pct >= 50 ? '--hot' : '--cool', underClass: pred.under_2_5_pct > pred.over_2_5_pct ? '--hot' : '--cool' },
    { label: 'Goals O/U 3.5', overLabel: 'Over', underLabel: 'Under',
      overPct: pred.over_3_5_pct, underPct: pred.under_3_5_pct,
      overClass: pred.over_3_5_pct >= 50 ? '--hot' : '--cool', underClass: pred.under_3_5_pct > pred.over_3_5_pct ? '--hot' : '--cool' },
    { label: 'BTTS', overLabel: 'Yes', underLabel: 'No',
      overPct: pred.btts_yes_pct, underPct: pred.btts_no_pct,
      overClass: pred.btts_yes_pct >= 50 ? '--hot' : '--cool', underClass: '--cool' },
    { label: 'Corners O/U 9.5', overLabel: 'Over', underLabel: 'Under',
      overPct: pred.over_9_5_corners_pct, underPct: pred.under_9_5_corners_pct,
      overClass: pred.over_9_5_corners_pct >= 50 ? '--hot' : '--cool', underClass: '--cool' },
    { label: 'Cards O/U 3.5', overLabel: 'Over', underLabel: 'Under',
      overPct: pred.over_3_5_cards_pct, underPct: pred.under_3_5_cards_pct,
      overClass: pred.over_3_5_cards_pct >= 50 ? '--hot' : '--cool', underClass: '--cool' },
    { label: 'Red Card', overLabel: 'Yes', underLabel: 'No',
      overPct: pred.red_card_pct, underPct: Math.round((100 - pred.red_card_pct) * 10) / 10,
      overClass: pred.red_card_pct > 30 ? '--hot' : '--cool', underClass: '--cool' },
  ]
}

function resultLabel(pred) {
  const max = Math.max(pred.home_win_pct, pred.draw_pct, pred.away_win_pct)
  if (max === pred.home_win_pct) return 'Home Win'
  if (max === pred.draw_pct) return 'Draw'
  return 'Away Win'
}

function resultPct(pred) {
  return Math.max(pred.home_win_pct, pred.draw_pct, pred.away_win_pct)
}

function resultClass(pred) {
  const max = Math.max(pred.home_win_pct, pred.draw_pct, pred.away_win_pct)
  if (max === pred.draw_pct) return '--draw'
  return '--win'
}

// ── Lifecycle ──────────────────────────────────────────────────────────────
onMounted(() => {
  loadFixtures()
  loadPredictions()
})

watch(activeTab, tab => {
  if (tab === 'standings' && !standings.value.length) loadStandings('SA')
})
</script>

<style scoped>
/* ── Reset & base ─────────────────────────────────────────────────────────── */
*{box-sizing:border-box}
.bv{min-height:100vh;background:#0d1117;color:#c9d1d9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:14px}
.dim{color:#6e7681}

/* ── Header ───────────────────────────────────────────────────────────────── */
.bv-header{background:#161b22;border-bottom:1px solid #21262d;display:flex;align-items:center;justify-content:space-between;padding:0 24px;height:52px;position:sticky;top:0;z-index:100}
.bv-header__brand{display:flex;align-items:center;gap:8px}
.bv-header__icon{font-size:1.3rem}
.bv-header__name{font-size:1rem;font-weight:700;color:#e6edf3}
.bv-header__powered{font-size:.72rem;color:#6e7681}
.bv-nav{display:flex;gap:2px}
.bv-nav__item{background:transparent;border:none;border-bottom:2px solid transparent;color:#8b949e;cursor:pointer;padding:6px 14px;font-size:.85rem;transition:all .15s}
.bv-nav__item.active{color:#58a6ff;border-bottom-color:#58a6ff}
.bv-nav__item:hover{color:#e6edf3}

/* ── Main ─────────────────────────────────────────────────────────────────── */
.bv-main{padding:20px 24px;max-width:1000px}

/* ── Toolbar / chips ──────────────────────────────────────────────────────── */
.bv-toolbar{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;flex-wrap:wrap;gap:8px}
.bv-chips{display:flex;gap:6px;flex-wrap:wrap}
.bv-chip{padding:4px 12px;border-radius:16px;border:1px solid #30363d;background:#161b22;color:#8b949e;cursor:pointer;font-size:.8rem;transition:all .15s}
.bv-chip.active{background:#1f6feb;border-color:#388bfd;color:#fff}

/* ── Fixtures grid ────────────────────────────────────────────────────────── */
.bv-fixture-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px}
.bv-fixture{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:14px 16px;cursor:pointer;transition:border-color .15s}
.bv-fixture:hover{border-color:#388bfd}
.bv-fixture--predicted{border-color:#238636}
.bv-fixture__top{display:flex;align-items:center;gap:6px;margin-bottom:10px;flex-wrap:wrap}
.bv-fixture__date{color:#6e7681;font-size:.78rem;margin-left:auto}
.bv-fixture__md{color:#6e7681;font-size:.75rem}
.bv-fixture__teams{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.bv-fixture__team{flex:1;font-size:.9rem;font-weight:500}
.bv-fixture__vs{color:#484f58;font-size:.78rem}
.bv-fixture__footer{display:flex;gap:6px;flex-wrap:wrap}

/* Quick odds strip */
.bv-fixture__odds{display:flex;gap:6px;margin-bottom:8px}
.bv-odd{padding:3px 8px;border-radius:5px;font-size:.82rem;font-weight:600}
.bv-odd--h{background:#1a2f4a;color:#79c0ff}
.bv-odd--d{background:#2a2a14;color:#e3b341}
.bv-odd--a{background:#1a3a1a;color:#56d364}

/* ── Badges ───────────────────────────────────────────────────────────────── */
.bv-badge{display:inline-flex;align-items:center;padding:2px 8px;border-radius:10px;font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.03em}
.bv-badge.sa{background:#1a2f1a;color:#3fb950;border:1px solid #238636}
.bv-badge.cl{background:#1a2340;color:#79c0ff;border:1px solid #1f6feb}
.bv-badge--green{background:#1a2f1a;color:#3fb950}
.bv-badge--yellow{background:#2a2510;color:#e3b341}
.bv-warning-badge{background:#2a1a10;color:#e3864a;border-radius:8px;padding:1px 6px;font-size:.72rem;font-weight:400}

/* ── State messages ───────────────────────────────────────────────────────── */
.bv-state{padding:40px;text-align:center;color:#6e7681}
.bv-state--loading{display:flex;align-items:center;gap:10px;justify-content:center;color:#8b949e}
.bv-state--error{color:#f85149;background:#1a0808;border-radius:8px;padding:16px}
.bv-state--warn{color:#e3b341;font-size:.85rem;padding:8px 0}

/* ── Spinner ──────────────────────────────────────────────────────────────── */
.bv-spinner{display:inline-block;border-radius:50%;border:2px solid #30363d;border-top-color:#58a6ff;animation:spin .7s linear infinite}
.bv-spinner{width:18px;height:18px}
.bv-spinner--xs{width:12px;height:12px}
@keyframes spin{to{transform:rotate(360deg)}}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
.bv-btn{display:inline-flex;align-items:center;gap:6px;padding:6px 14px;border-radius:6px;border:1px solid #30363d;background:#21262d;color:#c9d1d9;cursor:pointer;font-size:.85rem;transition:all .15s}
.bv-btn:hover{background:#30363d}
.bv-btn--ghost{background:transparent;border-color:transparent;color:#8b949e}
.bv-btn--ghost:hover{color:#e6edf3;background:#21262d}
.bv-btn--primary{background:#1f6feb;border-color:#388bfd;color:#fff}
.bv-btn--primary:hover{background:#388bfd}
.bv-btn--lg{padding:10px 24px;font-size:.95rem}
.bv-btn:disabled{opacity:.5;cursor:not-allowed}

/* ── Side panel ───────────────────────────────────────────────────────────── */
.bv-panel-overlay{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:200;display:flex;justify-content:flex-end}
.bv-panel{background:#0d1117;width:min(620px,100vw);height:100vh;overflow-y:auto;border-left:1px solid #21262d;padding:24px;position:relative}
.bv-panel__close{position:sticky;top:0;float:right;background:transparent;border:none;color:#6e7681;font-size:1.1rem;cursor:pointer;z-index:10}
.bv-panel__close:hover{color:#e6edf3}
.bv-panel__header{margin-bottom:20px}
.bv-panel__header h2{margin:6px 0 2px;font-size:1.1rem;color:#e6edf3}
.bv-panel__header h2 .dim{color:#484f58;font-size:.9rem}
.bv-panel__date{margin:0;font-size:.8rem;color:#6e7681}

/* ── Sections ─────────────────────────────────────────────────────────────── */
.bv-section{margin-bottom:28px}
.bv-section__title{font-size:.82rem;text-transform:uppercase;letter-spacing:.06em;color:#8b949e;font-weight:400;margin:0 0 12px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #21262d;padding-bottom:8px}

/* ── Odds table ───────────────────────────────────────────────────────────── */
.bv-odds-table{border-radius:8px;overflow:hidden;border:1px solid #21262d}
.bv-odds-row{display:flex;align-items:center;border-bottom:1px solid #21262d;font-size:.82rem}
.bv-odds-row:last-child{border-bottom:none}
.bv-odds-row--consensus{background:#161b22;font-weight:600}
.bv-odds-row__book{width:90px;padding:8px 10px;color:#6e7681;font-size:.78rem;flex-shrink:0}
.bv-odds-cell{flex:1;padding:8px 6px;text-align:center;font-size:.82rem;line-height:1.3}
.bv-odds-cell--h{color:#79c0ff}
.bv-odds-cell--d{color:#e3b341}
.bv-odds-cell--a{color:#56d364}

/* ── Prediction bars ──────────────────────────────────────────────────────── */
.bv-market{margin-bottom:16px}
.bv-market__lbl{font-size:.78rem;text-transform:uppercase;letter-spacing:.05em;color:#6e7681;margin-bottom:6px}
.bv-bar-row{display:flex;flex-direction:column;gap:5px}
.bv-bar-item{display:flex;align-items:center;gap:8px;font-size:.8rem}
.bv-bar-item span:first-child{width:40px;color:#8b949e}
.bv-bar-item span:last-child{width:38px;text-align:right;color:#8b949e}
.bv-bar-track{flex:1;height:7px;background:#21262d;border-radius:4px;overflow:hidden}
.bv-bar-fill{height:100%;border-radius:4px;transition:width .5s}
.bv-bar-fill.--win{background:linear-gradient(90deg,#1f6feb,#58a6ff)}
.bv-bar-fill.--draw{background:linear-gradient(90deg,#5e4a00,#e3b341)}

/* ── Market grid ──────────────────────────────────────────────────────────── */
.bv-markets-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-top:12px}
.bv-markets-grid--compact .bv-market-mini{padding:8px 10px}
.bv-market-mini{background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px}
.bv-market-mini__lbl{font-size:.72rem;color:#6e7681;text-transform:uppercase;letter-spacing:.04em;margin-bottom:8px}
.bv-pill-row{display:flex;gap:4px}
.bv-pill{flex:1;text-align:center;padding:5px 4px;border-radius:5px;font-size:.78rem;line-height:1.3}
.bv-pill.--hot{background:#1a3a1a;color:#3fb950}
.bv-pill.--cool{background:#21262d;color:#6e7681}

/* ── Scoreline ────────────────────────────────────────────────────────────── */
.bv-scoreline{display:flex;align-items:center;gap:10px;margin-top:14px;padding:8px 12px;background:#161b22;border-radius:8px;font-size:.85rem}
.bv-scoreline__val{font-size:1.1rem;font-weight:700;color:#58a6ff}
.bv-confidence{padding:2px 8px;border-radius:8px;font-size:.72rem;text-transform:uppercase;font-weight:600}
.bv-confidence.high{background:#1a3a1a;color:#3fb950}
.bv-confidence.medium{background:#2a2510;color:#e3b341}
.bv-confidence.low{background:#2a0e0e;color:#f85149}

/* ── Predict CTA ──────────────────────────────────────────────────────────── */
.bv-predict-cta{text-align:center;padding:20px 0}

/* ── News list ────────────────────────────────────────────────────────────── */
.bv-news-list{display:flex;flex-direction:column;gap:8px}
.bv-news-item{display:block;background:#161b22;border:1px solid #21262d;border-radius:8px;padding:12px;text-decoration:none;transition:border-color .15s}
.bv-news-item:hover{border-color:#388bfd}
.bv-news-item--injury{border-left:3px solid #da3633}
.bv-news-item__source{display:flex;align-items:center;gap:6px;margin-bottom:5px}
.bv-news-item__date{color:#6e7681;font-size:.75rem;margin-left:auto}
.bv-news-item__title{color:#c9d1d9;font-size:.88rem;line-height:1.4}
.bv-news-item__summary{color:#6e7681;font-size:.8rem;margin-top:4px;line-height:1.4}
.bv-source-badge{padding:1px 6px;border-radius:4px;font-size:.7rem;font-weight:600}
.bv-source-badge.bbc{background:#1a2a3a;color:#79c0ff}
.bv-source-badge.livescore{background:#1a3a1a;color:#3fb950}
.bv-source-badge.default{background:#21262d;color:#8b949e}

/* ── Predictions list ─────────────────────────────────────────────────────── */
.bv-pred-list{display:flex;flex-direction:column;gap:16px}
.bv-pred-card{background:#161b22;border:1px solid #21262d;border-radius:10px;padding:18px 20px}
.bv-pred-card__header{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px}
.bv-pred-card__header h3{margin:4px 0 2px;font-size:.95rem;color:#e6edf3}
.bv-pred-card__date{font-size:.75rem}
.bv-pred-card__result{margin-bottom:12px}
.bv-result-pill{display:inline-flex;align-items:center;gap:8px;padding:5px 12px;border-radius:20px;font-size:.85rem}
.bv-result-pill.--win{background:#1a2f4a;color:#79c0ff}
.bv-result-pill.--draw{background:#2a2510;color:#e3b341}
.bv-pred-card__odds{display:flex;align-items:center;gap:8px;margin-top:12px;padding-top:10px;border-top:1px solid #21262d;font-size:.82rem}

/* ── Standings table ──────────────────────────────────────────────────────── */
.bv-table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:16px}
.bv-table th{padding:7px 8px;text-align:right;color:#6e7681;font-weight:400;border-bottom:1px solid #21262d;font-size:.75rem;text-transform:uppercase}
.bv-table th:nth-child(-n+2){text-align:left}
.bv-table td{padding:8px 8px;text-align:right;border-bottom:1px solid #161b22}
.bv-table__club,.bv-table td:first-child{text-align:left}
.bv-table td.pts{font-weight:700;color:#e6edf3}
.bv-table td.pos{color:#3fb950}
.bv-table td.neg{color:#f85149}
.bv-table tr:hover td{background:#161b22}
.bv-form-row{display:flex;gap:3px;justify-content:flex-end}
.bv-dot{width:16px;height:16px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:.62rem;font-weight:700}
.bv-dot.W{background:#238636;color:#fff}
.bv-dot.D{background:#6e7681;color:#fff}
.bv-dot.L{background:#da3633;color:#fff}
</style>

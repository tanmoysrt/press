<script setup>
import {
	Button,
	createDocumentResource,
	createListResource,
	createResource,
	Dialog,
	ErrorMessage,
	Input,
	Spinner,
} from 'frappe-ui'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const router = useRouter()
const route = useRoute()

// ── Sidebar ───────────────────────────────────────────────────────────────────

const searchQuery = ref('')

const investigations = createListResource({
	doctype: 'Operational Investigation',
	fields: ['name', 'title', 'status', 'modified'],
	orderBy: 'modified desc',
	limit: 100,
	auto: true,
})

const filteredInvestigations = computed(() => {
	const list = investigations.data || []
	if (!searchQuery.value) return list
	const q = searchQuery.value.toLowerCase()
	return list.filter((i) => i.title?.toLowerCase().includes(q))
})

function groupByDate(list) {
	const today = new Date()
	today.setHours(0, 0, 0, 0)
	const yesterday = new Date(today)
	yesterday.setDate(yesterday.getDate() - 1)
	const groups = { Today: [], Yesterday: [], Older: [] }
	for (const item of list) {
		const d = new Date(item.modified)
		if (d >= today) groups.Today.push(item)
		else if (d >= yesterday) groups.Yesterday.push(item)
		else groups.Older.push(item)
	}
	return groups
}

const groupedInvestigations = computed(() =>
	groupByDate(filteredInvestigations.value),
)

function statusDot(status) {
	const map = {
		Running: { char: '●', cls: 'text-blue-500' },
		Queued: { char: '●', cls: 'text-blue-300' },
		Completed: { char: '○', cls: 'text-ink-gray-4' },
		Failed: { char: '✕', cls: 'text-red-500' },
		'Needs Human': { char: '△', cls: 'text-yellow-500' },
		'Action Recommended': { char: '△', cls: 'text-yellow-400' },
		'Action Taken': { char: '○', cls: 'text-green-500' },
	}
	return map[status] || { char: '○', cls: 'text-ink-gray-4' }
}

// ── Current investigation ─────────────────────────────────────────────────────

const investigationName = computed(() => route.params.name || null)

const investigation = createDocumentResource({
	doctype: 'Operational Investigation',
	name: investigationName.value || '__placeholder__',
	auto: false,
})

const logs = createListResource({
	doctype: 'Operational Investigation Log',
	filters: investigationName.value
		? { investigation: investigationName.value }
		: {},
	fields: ['name', 'type', 'title', 'content', 'data_json', 'timestamp'],
	orderBy: 'timestamp asc',
	limit: 200,
	auto: false,
})

// ── Polling ───────────────────────────────────────────────────────────────────

let pollInterval = null

function startPolling() {
	stopPolling()
	pollInterval = setInterval(() => {
		const status = investigation.doc?.status
		if (status === 'Running' || status === 'Queued') {
			investigation.reload()
			logs.reload()
		} else {
			stopPolling()
			investigations.reload()
		}
	}, 3000)
}

function stopPolling() {
	if (pollInterval) {
		clearInterval(pollInterval)
		pollInterval = null
	}
}

watch(
	investigationName,
	(name) => {
		if (name) {
			investigation.name = name
			logs.filters = { investigation: name }
			investigation.reload()
			logs.reload()
			startPolling()
		} else {
			stopPolling()
		}
	},
	{ immediate: true },
)

watch(
	() => investigation.doc?.status,
	(status) => {
		if (status === 'Running' || status === 'Queued') startPolling()
		else stopPolling()
	},
)

onUnmounted(stopPolling)

// ── Chat thread ───────────────────────────────────────────────────────────────

const expandedTools = ref(new Set())

function toggleTool(logName) {
	if (expandedTools.value.has(logName)) expandedTools.value.delete(logName)
	else expandedTools.value.add(logName)
}

const chatMessages = computed(() => {
	return (logs.data || []).filter((l) =>
		[
			'message',
			'finding',
			'tool_call',
			'hypothesis',
			'action_plan',
			'action_result',
			'rca',
		].includes(l.type),
	)
})

// ── Composer ──────────────────────────────────────────────────────────────────

const composer = ref('')
const isRunning = computed(
	() =>
		investigation.doc?.status === 'Running' ||
		investigation.doc?.status === 'Queued',
)

const startInv = createResource({
	url: 'press.api.ai_investigator.start_investigation',
})
const continueInv = createResource({
	url: 'press.api.ai_investigator.continue_investigation',
})
const finalizeRca = createResource({
	url: 'press.api.ai_investigator.finalize_rca',
})

async function send() {
	const text = composer.value.trim()
	if (!text) return
	composer.value = ''
	if (!investigationName.value) {
		await startInv.submit({ query: text })
		if (startInv.data) {
			router.push({ name: 'AI Investigation', params: { name: startInv.data } })
		}
	} else {
		await continueInv.submit({
			investigation_name: investigationName.value,
			instruction: text,
		})
		logs.reload()
		investigation.reload()
	}
}

function handleKey(e) {
	if (e.key === 'Enter' && !e.shiftKey) {
		e.preventDefault()
		send()
	}
}

async function generateRca() {
	await finalizeRca.submit({ investigation_name: investigationName.value })
	logs.reload()
}

// ── Suggestion chips ──────────────────────────────────────────────────────────

const suggestions = [
	{ label: 'Investigate an incident', text: 'Investigate incident ' },
	{ label: 'Check a site', text: 'Check site performance for ' },
	{ label: 'Check a server', text: 'Check server performance for ' },
	{ label: 'Why was X slow?', text: 'Why was ' },
]

function useSuggestion(text) {
	composer.value = text
}

// ── Action plan approval ──────────────────────────────────────────────────────

const showApproveModal = ref(false)
const pendingAction = ref(null)
const storedToken = ref('')
const actionTokens = ref({})

const executeAction = createResource({
	url: 'press.api.ai_investigator.execute_action_plan',
})

watch(
	() => continueInv.data,
	(result) => {
		if (result?.action_id && result?.approval_token) {
			actionTokens.value[result.action_id] = result.approval_token
		}
	},
)

function openApproveModal(log) {
	const data = log.data_json || {}
	pendingAction.value = { log, data }
	storedToken.value = actionTokens.value[log.name] || ''
	showApproveModal.value = true
}

async function confirmApprove() {
	if (!pendingAction.value) return
	const { log } = pendingAction.value
	await executeAction.submit({
		investigation_name: investigationName.value,
		action_id: log.name,
		approval_token: storedToken.value,
	})
	showApproveModal.value = false
	pendingAction.value = null
	storedToken.value = ''
	logs.reload()
	investigation.reload()
}
</script>

<template>
	<div class="flex h-screen overflow-hidden">
		<!-- Left sidebar -->
		<div
			class="flex w-60 flex-shrink-0 flex-col border-r border-outline-gray-2 bg-surface-white"
		>
			<div class="flex items-center justify-between px-3 py-3">
				<span class="text-sm font-semibold text-ink-gray-9">AI Ops</span>
				<Button size="sm" variant="ghost" :route="{ name: 'AI Investigator' }">
					<template #prefix><LucidePlus class="size-4" /></template>
				</Button>
			</div>
			<div class="px-2 pb-2">
				<Input v-model="searchQuery" size="sm" placeholder="Search..." />
			</div>
			<div class="flex-1 overflow-y-auto">
				<Spinner
					v-if="investigations.loading && !investigations.data"
					class="mx-auto mt-6 h-5"
				/>
				<template v-for="(items, group) in groupedInvestigations" :key="group">
					<div
						v-if="items.length"
						class="px-3 pb-1 pt-3 text-xs font-medium text-ink-gray-4"
					>
						{{ group }}
					</div>
					<button
						v-for="item in items"
						:key="item.name"
						class="flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left hover:bg-surface-gray-1"
						:class="{
							'bg-surface-gray-2': item.name === investigationName,
						}"
						@click="
							router.push({
								name: 'AI Investigation',
								params: { name: item.name },
							})
						"
					>
						<span
							:class="statusDot(item.status).cls"
							class="text-xs leading-none"
							>{{ statusDot(item.status).char }}</span
						>
						<span class="truncate text-sm text-ink-gray-7"
							>{{ item.title }}</span
						>
					</button>
				</template>
			</div>
		</div>

		<!-- Chat panel -->
		<div class="flex flex-1 flex-col overflow-hidden">
			<!-- Thread header -->
			<div
				v-if="investigation.doc"
				class="flex items-center justify-between border-b border-outline-gray-2 px-5 py-3"
			>
				<span class="font-medium text-ink-gray-9"
					>{{ investigation.doc.title }}</span
				>
				<span
					v-if="isRunning"
					class="flex items-center gap-1.5 text-sm text-blue-500"
				>
					<LucideLoader class="size-4 animate-spin" />
					Running...
				</span>
			</div>

			<!-- Messages area -->
			<div class="flex-1 space-y-4 overflow-y-auto px-6 py-4">
				<!-- Empty state -->
				<template v-if="!investigationName">
					<div
						class="flex h-full flex-col items-center justify-center gap-6 text-center"
					>
						<div>
							<LucideBotMessageSquare
								class="mx-auto mb-3 size-10 text-ink-gray-4"
							/>
							<h2 class="text-lg font-semibold text-ink-gray-9">
								FC AI Assistant
							</h2>
							<p class="text-sm text-ink-gray-5">System Manager only</p>
						</div>
						<p class="text-ink-gray-6">What do you want to investigate?</p>
						<div class="flex flex-wrap justify-center gap-2">
							<Button
								v-for="s in suggestions"
								:key="s.label"
								variant="outline"
								size="sm"
								@click="useSuggestion(s.text)"
								>{{ s.label }}</Button
							>
						</div>
					</div>
				</template>

				<!-- Chat messages -->
				<template v-else>
					<Spinner
						v-if="logs.loading && !logs.data"
						class="mx-auto mt-10 h-6"
					/>

					<template v-for="log in chatMessages" :key="log.name">
						<!-- User message -->
						<div
							v-if="log.type === 'message' && log.title === 'User'"
							class="flex justify-end"
						>
							<div
								class="max-w-lg rounded-lg bg-surface-gray-2 px-4 py-2 text-sm text-ink-gray-9"
							>
								{{ log.content }}
							</div>
						</div>

						<!-- Assistant message -->
						<div
							v-else-if="
								log.type === 'message' && log.title === 'Assistant'
							"
							class="flex gap-3"
						>
							<LucideBotMessageSquare
								class="mt-0.5 size-5 flex-shrink-0 text-ink-gray-5"
							/>
							<div class="whitespace-pre-wrap text-sm text-ink-gray-9">
								{{ log.content }}
							</div>
						</div>

						<!-- Tool call row -->
						<div v-else-if="log.type === 'tool_call'" class="ml-8">
							<button
								class="flex items-center gap-2 text-xs text-ink-gray-5 hover:text-ink-gray-7"
								@click="toggleTool(log.name)"
							>
								<component
									:is="
										expandedTools.has(log.name)
											? LucideChevronDown
											: LucideChevronRight
									"
									class="size-3"
								/>
								<span class="font-mono">{{ log.title }}</span>
								<LucideCheck
									v-if="log.data_json?.status === 'success'"
									class="size-3 text-green-500"
								/>
								<span v-if="log.data_json?.duration_ms" class="text-ink-gray-4"
									>{{ log.data_json.duration_ms }}ms</span
								>
							</button>
							<div
								v-if="expandedTools.has(log.name)"
								class="mt-1 rounded border border-outline-gray-2 bg-surface-gray-1 p-3 text-xs text-ink-gray-7"
							>
								<div class="mb-1 text-ink-gray-5">
									{{ JSON.stringify(log.data_json?.input || {}) }}
								</div>
								<hr class="my-1 border-outline-gray-2" />
								<div>{{ log.data_json?.output_summary }}</div>
							</div>
						</div>

						<!-- Finding -->
						<div
							v-else-if="log.type === 'finding'"
							class="ml-8 text-xs italic text-ink-gray-6"
						>
							{{ log.title }}
						</div>

						<!-- Action plan card -->
						<div v-else-if="log.type === 'action_plan'" class="ml-8">
							<div class="rounded-lg border border-outline-gray-2 p-4 text-sm">
								<div class="font-medium text-ink-gray-9">
									Action: {{ log.data_json?.action }}
									{{ log.data_json?.target_name }}
								</div>
								<div class="mt-1 text-ink-gray-6">
									Reason: {{ log.data_json?.reason }}
								</div>
								<div class="text-ink-gray-6">
									Impact: {{ log.data_json?.expected_impact }}
								</div>
								<div class="mt-1 text-xs text-ink-gray-4">
									Expires: {{ log.data_json?.expires_at }}
								</div>
								<div
									v-if="log.data_json?.status === 'pending_approval'"
									class="mt-3 flex justify-end"
								>
									<Button
										size="sm"
										variant="solid"
										theme="blue"
										@click="openApproveModal(log)"
										>Approve</Button
									>
								</div>
								<div
									v-else
									class="mt-2 text-xs font-medium"
									:class="
										log.data_json?.status === 'executed'
											? 'text-green-600'
											: 'text-ink-gray-5'
									"
								>
									{{ log.data_json?.status }}
								</div>
							</div>
						</div>

						<!-- RCA block -->
						<div v-else-if="log.type === 'rca'" class="ml-2">
							<div class="rounded-lg border border-outline-gray-2 p-4">
								<div
									class="prose prose-sm max-w-none whitespace-pre-wrap text-ink-gray-9"
								>
									{{ log.content }}
								</div>
								<div class="mt-3 flex gap-2">
									<Button
										size="sm"
										variant="outline"
										@click="navigator.clipboard.writeText(log.content)"
										>Copy RCA</Button
									>
								</div>
							</div>
						</div>
					</template>

					<!-- Summary card -->
					<div
						v-if="
							investigation.doc &&
							!isRunning &&
							investigation.doc.primary_cause
						"
						class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-4"
					>
						<div
							class="flex items-center gap-2 text-sm font-medium text-ink-gray-7"
						>
							<span>{{ investigation.doc.status }}</span>
							<span v-if="investigation.doc.confidence" class="text-ink-gray-5">
								·
								{{ Math.round(investigation.doc.confidence * 100) }}% confident
							</span>
						</div>
						<div class="mt-1 text-sm text-ink-gray-9">
							Cause: {{ investigation.doc.primary_cause }}
						</div>
						<div class="mt-3 flex gap-2">
							<Button
								size="sm"
								variant="outline"
								:loading="finalizeRca.loading"
								@click="generateRca"
							>
								Generate RCA
							</Button>
						</div>
					</div>
				</template>
			</div>

			<!-- Composer -->
			<div class="border-t border-outline-gray-2 p-4">
				<div class="flex gap-2">
					<Input
						v-model="composer"
						:placeholder="
							investigationName
								? 'Ask a follow-up...'
								: 'Ask about a site, server, bench, incident...'
						"
						:disabled="isRunning"
						class="flex-1"
						@keydown="handleKey"
					/>
					<Button
						variant="solid"
						theme="blue"
						:disabled="isRunning || !composer.trim()"
						@click="send"
						>Send</Button
					>
				</div>
				<p v-if="isRunning" class="mt-1.5 text-xs text-ink-gray-4">
					Disabled while investigation is running...
				</p>
			</div>
		</div>
	</div>

	<!-- Approve action modal -->
	<Dialog v-model="showApproveModal" :options="{ title: 'Confirm Action' }">
		<template #body-content>
			<div v-if="pendingAction" class="space-y-3 text-sm">
				<div class="font-medium text-ink-gray-9">
					{{ pendingAction.data.action }} {{ pendingAction.data.target_name }}
				</div>
				<div class="grid grid-cols-[100px_1fr] gap-1 text-ink-gray-6">
					<span>Reason</span><span>{{ pendingAction.data.reason }}</span>
					<span>Impact</span
					><span>{{ pendingAction.data.expected_impact }}</span>
					<span>Expires</span><span>{{ pendingAction.data.expires_at }}</span>
				</div>
				<ErrorMessage
					v-if="executeAction.error"
					:message="executeAction.error"
				/>
			</div>
		</template>
		<template #actions>
			<Button variant="ghost" @click="showApproveModal = false">Cancel</Button>
			<Button
				variant="solid"
				theme="red"
				:loading="executeAction.loading"
				@click="confirmApprove"
			>
				Approve & Run
			</Button>
		</template>
	</Dialog>
</template>

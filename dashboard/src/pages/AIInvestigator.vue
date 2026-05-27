<script setup>
import {
	Badge,
	Button,
	createDocumentResource,
	createListResource,
	createResource,
	Dialog,
	ErrorMessage,
	LoadingIndicator,
	Textarea,
	TextInput,
} from 'frappe-ui'
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { toast } from 'vue-sonner'

const router = useRouter()
const route = useRoute()

// ── Helpers ───────────────────────────────────────────────────────────────────

function parseJson(value) {
	if (!value) return {}
	if (typeof value === 'object') return value
	try {
		return JSON.parse(value)
	} catch {
		return {}
	}
}

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

const STATUS_BADGE = {
	Running: { label: 'Running', theme: 'blue' },
	Queued: { label: 'Queued', theme: 'blue' },
	Completed: { label: 'Completed', theme: 'green' },
	Failed: { label: 'Failed', theme: 'red' },
	'Needs Human': { label: 'Needs Human', theme: 'yellow' },
	'Action Recommended': { label: 'Action Recommended', theme: 'yellow' },
	'Action Taken': { label: 'Action Taken', theme: 'green' },
}

function statusBadge(status) {
	return STATUS_BADGE[status] || { label: status || 'Unknown', theme: 'gray' }
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
		// Keep polling while running/queued, or while doc hasn't loaded yet
		if (!investigation.doc || status === 'Running' || status === 'Queued') {
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
			logs.update({ filters: { investigation: name } })
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
		else if (status) stopPolling()
	},
)

onUnmounted(stopPolling)

// ── Chat thread ───────────────────────────────────────────────────────────────

const chatEnd = ref(null)
const expandedTools = ref(new Set())

function toggleTool(logName) {
	const s = new Set(expandedTools.value)
	if (s.has(logName)) s.delete(logName)
	else s.add(logName)
	expandedTools.value = s
}

const LOG_TYPES = [
	'message',
	'finding',
	'tool_call',
	'hypothesis',
	'action_plan',
	'action_result',
	'rca',
	'error',
]

const chatMessages = computed(() =>
	(logs.data || [])
		.filter((l) => LOG_TYPES.includes(l.type))
		.map((l) => ({ ...l, data: parseJson(l.data_json) })),
)

watch(chatMessages, () => {
	nextTick(() => chatEnd.value?.scrollIntoView({ behavior: 'smooth' }))
})

// ── Composer ──────────────────────────────────────────────────────────────────

const composer = ref('')
const isRunning = computed(
	() =>
		investigation.doc?.status === 'Running' ||
		investigation.doc?.status === 'Queued' ||
		continueInv.loading,
)

const startInv = createResource({
	url: 'press.api.ai_investigator.start_investigation',
	method: 'POST',
})
const continueInv = createResource({
	url: 'press.api.ai_investigator.continue_investigation',
	method: 'POST',
})
const finalizeRca = createResource({
	url: 'press.api.ai_investigator.finalize_rca',
	method: 'POST',
})

async function send() {
	const text = composer.value.trim()
	if (!text || isRunning.value) return
	composer.value = ''
	if (!investigationName.value) {
		await startInv.submit({ query: text })
		if (startInv.error) {
			toast.error(startInv.error)
			return
		}
		if (startInv.data) {
			router.push({ name: 'AI Investigation', params: { name: startInv.data } })
		}
	} else {
		await continueInv.submit({
			investigation_name: investigationName.value,
			instruction: text,
		})
		if (continueInv.error) {
			toast.error(continueInv.error)
			return
		}
		if (continueInv.data?.action_id && continueInv.data?.approval_token) {
			actionTokens.value[continueInv.data.action_id] =
				continueInv.data.approval_token
		}
		logs.reload()
		investigation.reload()
		startPolling()
	}
}

function handleComposerKey(e) {
	if (e.key === 'Enter' && !e.shiftKey) {
		e.preventDefault()
		send()
	}
}

async function generateRca() {
	await finalizeRca.submit({ investigation_name: investigationName.value })
	if (finalizeRca.error) {
		toast.error(finalizeRca.error)
		return
	}
	logs.reload()
}

// ── Suggestion chips ──────────────────────────────────────────────────────────

const suggestions = [
	{ label: 'Investigate incident', text: 'Investigate incident ' },
	{ label: 'Check site', text: 'Check site performance for ' },
	{ label: 'Check server', text: 'Check server performance for ' },
	{ label: 'Why was X slow?', text: 'Why was ' },
]

// ── Action plan approval ──────────────────────────────────────────────────────

const showApproveModal = ref(false)
const pendingAction = ref(null)
const actionTokens = ref({})

const executeAction = createResource({
	url: 'press.api.ai_investigator.execute_action_plan',
	method: 'POST',
})

function openApproveModal(log) {
	pendingAction.value = log
	showApproveModal.value = true
}

async function confirmApprove() {
	if (!pendingAction.value) return
	const log = pendingAction.value
	const token = actionTokens.value[log.name] || ''
	if (!token) {
		toast.error(
			'Approval token not found. Re-run the investigation to get a new token.',
		)
		return
	}
	await executeAction.submit({
		investigation_name: investigationName.value,
		action_id: log.name,
		approval_token: token,
	})
	if (executeAction.error) {
		toast.error(executeAction.error)
		return
	}
	showApproveModal.value = false
	pendingAction.value = null
	delete actionTokens.value[log.name]
	logs.reload()
	investigation.reload()
}
</script>

<template>
	<div class="flex h-full overflow-hidden">
		<!-- Sidebar -->
		<div
			class="flex w-56 flex-shrink-0 flex-col border-r border-outline-gray-2 bg-surface-white"
		>
			<!-- Sidebar header -->
			<div class="flex items-center justify-between px-3 py-2.5">
				<span class="text-sm font-semibold text-ink-gray-9">AI Ops</span>
				<Button
					variant="ghost"
					size="sm"
					:route="{ name: 'AI Investigator' }"
					label="New"
				>
					<template #icon>
						<LucidePlus class="size-4" />
					</template>
				</Button>
			</div>

			<!-- Search -->
			<div class="px-2 pb-2">
				<TextInput
					v-model="searchQuery"
					size="sm"
					placeholder="Search..."
					:debounce="200"
				/>
			</div>

			<!-- List -->
			<div class="flex-1 overflow-y-auto">
				<LoadingIndicator
					v-if="investigations.loading && !investigations.data"
					class="mx-auto mt-6 h-5 w-5"
				/>
				<template v-for="(items, group) in groupedInvestigations" :key="group">
					<div
						v-if="items.length"
						class="px-3 pb-0.5 pt-2.5 text-xs font-medium text-ink-gray-4"
					>
						{{ group }}
					</div>
					<div
						v-for="item in items"
						:key="item.name"
						class="mx-1 flex cursor-pointer items-start gap-2 rounded px-2 py-1.5 hover:bg-surface-gray-2"
						:class="{ 'bg-surface-gray-2': item.name === investigationName }"
						@click="router.push({ name: 'AI Investigation', params: { name: item.name } })"
					>
						<span class="mt-0.5 flex-shrink-0">
							<span
								class="inline-block size-2 rounded-full"
								:class="{
									'bg-blue-500': item.status === 'Running' || item.status === 'Queued',
									'bg-green-500': item.status === 'Completed' || item.status === 'Action Taken',
									'bg-red-500': item.status === 'Failed',
									'bg-yellow-500':
										item.status === 'Needs Human' || item.status === 'Action Recommended',
									'bg-ink-gray-3': !item.status,
								}"
							/>
						</span>
						<span class="truncate text-sm text-ink-gray-8"
							>{{ item.title }}</span
						>
					</div>
				</template>
				<div
					v-if="!investigations.loading && !filteredInvestigations.length"
					class="px-4 py-6 text-center text-sm text-ink-gray-4"
				>
					No investigations
				</div>
			</div>
		</div>

		<!-- Chat panel -->
		<div class="flex flex-1 flex-col overflow-hidden bg-surface-white">
			<!-- Thread header -->
			<div
				v-if="investigationName"
				class="flex flex-shrink-0 items-center justify-between border-b border-outline-gray-2 px-5 py-3"
			>
				<div class="flex items-center gap-3 overflow-hidden">
					<span class="truncate font-medium text-ink-gray-9">
						{{ investigation.doc?.title || investigationName }}
					</span>
					<Badge
						v-if="investigation.doc?.status"
						:label="statusBadge(investigation.doc.status).label"
						:theme="statusBadge(investigation.doc.status).theme"
						size="sm"
					/>
				</div>
				<div class="ml-4 flex items-center gap-2">
					<LoadingIndicator v-if="isRunning" class="h-4 w-4 text-blue-500" />
					<Button
						v-if="
							investigation.doc &&
							!isRunning &&
							investigation.doc.primary_cause &&
							!investigation.doc.rca_markdown
						"
						size="sm"
						variant="outline"
						:loading="finalizeRca.loading"
						@click="generateRca"
					>
						Generate RCA
					</Button>
				</div>
			</div>

			<!-- Messages -->
			<div class="flex-1 overflow-y-auto px-5 py-4">
				<!-- Empty state — no investigation selected -->
				<div
					v-if="!investigationName"
					class="flex h-full flex-col items-center justify-center gap-5 text-center"
				>
					<div>
						<LucideBotMessageSquare
							class="mx-auto mb-3 size-10 text-ink-gray-3"
						/>
						<h2 class="text-base font-semibold text-ink-gray-9">
							AI Ops Investigator
						</h2>
						<p class="mt-1 text-sm text-ink-gray-5">System Manager only</p>
					</div>
					<p class="text-sm text-ink-gray-6">
						What would you like to investigate?
					</p>
					<div class="flex flex-wrap justify-center gap-2">
						<Button
							v-for="s in suggestions"
							:key="s.label"
							variant="outline"
							size="sm"
							@click="composer = s.text"
						>
							{{ s.label }}
						</Button>
					</div>
				</div>

				<!-- Loading logs -->
				<div
					v-else-if="logs.loading && !logs.data"
					class="flex h-full items-center justify-center"
				>
					<LoadingIndicator class="h-6 w-6 text-ink-gray-4" />
				</div>

				<!-- Chat messages -->
				<template v-else>
					<div class="space-y-4">
						<template v-for="log in chatMessages" :key="log.name">
							<!-- User message -->
							<div
								v-if="log.type === 'message' && log.title === 'User'"
								class="flex justify-end"
							>
								<div
									class="max-w-lg rounded-lg bg-surface-gray-2 px-4 py-2.5 text-sm text-ink-gray-9"
								>
									{{ log.content }}
								</div>
							</div>

							<!-- Assistant message -->
							<div
								v-else-if="log.type === 'message' && log.title === 'Assistant'"
								class="flex gap-3"
							>
								<div
									class="flex size-7 flex-shrink-0 items-center justify-center rounded-full bg-surface-gray-2"
								>
									<LucideBotMessageSquare class="size-4 text-ink-gray-6" />
								</div>
								<div
									class="whitespace-pre-wrap text-sm leading-relaxed text-ink-gray-9"
								>
									{{ log.content }}
								</div>
							</div>

							<!-- Tool call -->
							<div v-else-if="log.type === 'tool_call'" class="ml-10">
								<button
									class="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-ink-gray-5 hover:bg-surface-gray-1 hover:text-ink-gray-7"
									@click="toggleTool(log.name)"
								>
									<component
										:is="expandedTools.has(log.name) ? LucideChevronDown : LucideChevronRight"
										class="size-3 flex-shrink-0"
									/>
									<span class="font-mono">{{ log.title }}</span>
									<LucideCheck
										v-if="log.data?.status === 'success'"
										class="size-3 text-green-500"
									/>
									<span v-if="log.data?.duration_ms" class="text-ink-gray-4">
										{{ log.data.duration_ms }}ms
									</span>
								</button>
								<div
									v-if="expandedTools.has(log.name)"
									class="mt-1 ml-2 rounded-md border border-outline-gray-2 bg-surface-gray-1 p-3 text-xs"
								>
									<p class="mb-1 font-mono text-ink-gray-5">
										{{ JSON.stringify(log.data?.input || {}) }}
									</p>
									<hr class="my-1.5 border-outline-gray-2" />
									<p class="text-ink-gray-7">{{ log.data?.output_summary }}</p>
								</div>
							</div>

							<!-- Finding -->
							<div
								v-else-if="log.type === 'finding'"
								class="ml-10 flex items-start gap-2 text-sm text-ink-gray-6"
							>
								<LucideInfo
									class="mt-0.5 size-3.5 flex-shrink-0 text-blue-400"
								/>
								{{ log.title }}
							</div>

							<!-- Hypothesis -->
							<div
								v-else-if="log.type === 'hypothesis'"
								class="ml-10 flex items-start gap-2 text-sm text-ink-gray-6"
							>
								<LucideLightbulb
									class="mt-0.5 size-3.5 flex-shrink-0 text-yellow-500"
								/>
								<span>
									{{ log.title }}
									<span
										v-if="log.data?.confidence"
										class="ml-1 text-xs text-ink-gray-4"
									>
										({{ Math.round(log.data.confidence * 100) }}%)
									</span>
								</span>
							</div>

							<!-- Action plan card -->
							<div v-else-if="log.type === 'action_plan'" class="ml-10">
								<div
									class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-4 text-sm"
								>
									<div class="flex items-start justify-between gap-3">
										<div>
											<p class="font-medium text-ink-gray-9">
												{{ log.data?.action }}
												— {{ log.data?.target_name }}
											</p>
											<p class="mt-1 text-ink-gray-6">{{ log.data?.reason }}</p>
											<p class="text-ink-gray-5">
												Impact: {{ log.data?.expected_impact }}
											</p>
											<p class="mt-1 text-xs text-ink-gray-4">
												Expires: {{ log.data?.expires_at }}
											</p>
										</div>
										<div class="flex-shrink-0">
											<Badge
												v-if="log.data?.status !== 'pending_approval'"
												:label="log.data?.status"
												:theme="log.data?.status === 'executed' ? 'green' : 'gray'"
												size="sm"
											/>
											<Button
												v-else
												size="sm"
												variant="solid"
												theme="red"
												@click="openApproveModal(log)"
											>
												Approve
											</Button>
										</div>
									</div>
								</div>
							</div>

							<!-- Action result -->
							<div
								v-else-if="log.type === 'action_result'"
								class="ml-10 flex items-start gap-2 text-sm text-green-700"
							>
								<LucideCheckCircle class="mt-0.5 size-3.5 flex-shrink-0" />
								{{ log.title }}
							</div>

							<!-- Error -->
							<div
								v-else-if="log.type === 'error'"
								class="ml-10 flex items-start gap-2 text-sm text-red-600"
							>
								<LucideAlertCircle class="mt-0.5 size-3.5 flex-shrink-0" />
								<span
									>{{ log.title }}
									<span v-if="log.content">: {{ log.content }}</span></span
								>
							</div>

							<!-- RCA -->
							<div v-else-if="log.type === 'rca'">
								<div class="rounded-lg border border-outline-gray-2 p-5">
									<div class="mb-3 flex items-center justify-between">
										<span class="text-sm font-semibold text-ink-gray-9"
											>Root Cause Analysis</span
										>
										<Button
											size="sm"
											variant="ghost"
											@click="navigator.clipboard.writeText(log.content)"
										>
											<template #icon>
												<LucideCopy class="size-3.5" />
											</template>
										</Button>
									</div>
									<div
										class="whitespace-pre-wrap text-sm leading-relaxed text-ink-gray-8"
									>
										{{ log.content }}
									</div>
								</div>
							</div>
						</template>

						<!-- Summary card (shown after completion if RCA not generated yet) -->
						<div
							v-if="
								investigation.doc &&
								!isRunning &&
								investigation.doc.primary_cause &&
								!investigation.doc.rca_markdown
							"
							class="rounded-lg border border-outline-gray-2 bg-surface-gray-1 p-4"
						>
							<div class="flex items-center gap-2">
								<LucideAlertCircle class="size-4 text-yellow-500" />
								<span class="text-sm font-medium text-ink-gray-7">
									{{ investigation.doc.status }}
									<span
										v-if="investigation.doc.confidence"
										class="font-normal text-ink-gray-5"
									>
										· {{ Math.round(investigation.doc.confidence * 100) }}%
										confident
									</span>
								</span>
							</div>
							<p class="mt-1 text-sm text-ink-gray-9">
								{{ investigation.doc.primary_cause }}
							</p>
						</div>

						<!-- Typing indicator while running -->
						<div v-if="isRunning" class="flex items-center gap-3">
							<div
								class="flex size-7 items-center justify-center rounded-full bg-surface-gray-2"
							>
								<LucideBotMessageSquare class="size-4 text-ink-gray-6" />
							</div>
							<div class="flex gap-1">
								<span
									class="size-1.5 animate-bounce rounded-full bg-ink-gray-4 [animation-delay:0ms]"
								/>
								<span
									class="size-1.5 animate-bounce rounded-full bg-ink-gray-4 [animation-delay:150ms]"
								/>
								<span
									class="size-1.5 animate-bounce rounded-full bg-ink-gray-4 [animation-delay:300ms]"
								/>
							</div>
						</div>
					</div>

					<div ref="chatEnd" class="h-1" />
				</template>
			</div>

			<!-- Composer -->
			<div
				class="flex-shrink-0 border-t border-outline-gray-2 bg-surface-white p-3"
			>
				<div class="flex items-end gap-2">
					<Textarea
						v-model="composer"
						class="flex-1"
						:rows="1"
						:placeholder="
							investigationName
								? 'Ask a follow-up... (Enter to send, Shift+Enter for newline)'
								: 'Describe what you want to investigate...'
						"
						:disabled="isRunning || startInv.loading"
						@keydown="handleComposerKey"
					/>
					<Button
						variant="solid"
						theme="blue"
						:disabled="isRunning || !composer.trim() || startInv.loading"
						:loading="continueInv.loading || startInv.loading"
						@click="send"
					>
						Send
					</Button>
				</div>
				<ErrorMessage
					v-if="startInv.error || continueInv.error"
					class="mt-2"
					:message="startInv.error || continueInv.error"
				/>
			</div>
		</div>
	</div>

	<!-- Approve action modal -->
	<Dialog
		v-model="showApproveModal"
		:options="{
			title: 'Confirm Action',
			size: 'sm',
			actions: [
				{
					label: 'Cancel',
					variant: 'ghost',
					onClick: () => { showApproveModal = false; pendingAction = null },
				},
				{
					label: 'Approve & Execute',
					variant: 'solid',
					theme: 'red',
					loading: executeAction.loading,
					onClick: confirmApprove,
				},
			],
		}"
	>
		<template #body-content>
			<div v-if="pendingAction" class="space-y-3 text-sm">
				<div>
					<p class="font-medium text-ink-gray-9">
						{{ pendingAction.data?.action }}
						on {{ pendingAction.data?.target_name }}
					</p>
					<p class="mt-1 text-ink-gray-6">{{ pendingAction.data?.reason }}</p>
				</div>
				<div class="rounded-md bg-surface-gray-1 p-3 text-xs text-ink-gray-6">
					<p>
						<span class="font-medium">Expected impact:</span>
						{{ pendingAction.data?.expected_impact }}
					</p>
					<p class="mt-1">
						<span class="font-medium">Expires:</span>
						{{ pendingAction.data?.expires_at }}
					</p>
				</div>
				<ErrorMessage
					v-if="executeAction.error"
					:message="executeAction.error"
				/>
				<div
					v-if="!actionTokens[pendingAction?.name]"
					class="rounded-md bg-surface-yellow-1 p-3 text-xs text-yellow-800"
				>
					Approval token not available. Only actions initiated in this session
					can be approved.
				</div>
			</div>
		</template>
	</Dialog>
</template>

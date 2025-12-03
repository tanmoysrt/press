<template>
	<div :class="{
		'relative h-[100%]': this.$resources?.timeline?.loading,
	}">
		<Header class="sticky top-0 z-10 bg-white">
			<div class="flex w-full flex-col gap-2 md:flex-row md:items-center md:justify-between">
				<div class="flex flex-row items-center gap-2">
					<Breadcrumbs :items="[
						{ label: 'Dev Tools', route: '/binlog-browser' },
						{ label: 'Binlog Browser', route: '/binlog-browser' },
					]" />
				</div>

				<div class="flex flex-row gap-2">
					<Tooltip text="This is an experimental feature">
						<div class="rounded-md bg-purple-100 p-1.5">
							<lucide-flask-conical class="h-4 w-4 text-purple-500" />
						</div>
					</Tooltip>
					<LinkControl class="cursor-pointer" :options="{ doctype: 'Site', filters: { status: 'Active' } }"
						placeholder="Select a site" v-model="site" />
				</div>
			</div>
		</Header>
		<div class="mx-5 my-2.5">
			<div v-if="!site" class="flex h-full min-h-[80vh] w-full items-center justify-center gap-2 text-gray-700">
				Select a site to get started
			</div>
			<div class="mt-2 flex flex-col" v-else>
				<!-- Time and Query Selector -->
				<div class="flex flex-row items-center justify-between gap-2">
					<div class="flex flex-row items-center gap-2">
						<div class="text-base">Query</div>
						<FormControl type="select" :options="[
							{ label: 'ALL     ', value: 'ALL' },
							{ label: 'INSERT  ', value: 'INSERT' },
							{ label: 'UPDATE  ', value: 'UPDATE' },
							{ label: 'DELETE  ', value: 'DELETE' },
							{ label: 'SELECT  ', value: 'SELECT' },
							{ label: 'OTHER   ', value: 'OTHER' },
						]" size="sm" variant="outline" placeholder="Query Type" v-model="type" />
					</div>
					<div class="flex flex-row items-center gap-2">
						<div class="max-w-[11rem] text-base" :autoClose="true">
							<DatTimePicker v-model="start" variant="outline" placeholder="Start Time" />
						</div>
						<FeatherIcon name="arrow-right" class="h-5 w-5 stroke-gray-700" />
						<div class="max-w-[11rem] text-base" :autoClose="true">
							<DatTimePicker v-model="end" variant="outline" placeholder="End Time" />
						</div>
					</div>
				</div>
				<!-- Timeline chart -->
				<div class="max-w-100 py-2">
					<BinlogBrowserChart :data="barChartData" @zoomEvent="onZoomEvent" />
				</div>
				<div class="relative">
					<!-- Query Option -->
					<div class="mt-3 flex flex-row items-center justify-between gap-2">
						<div class="flex flex-row items-center gap-2">
							<div class="text-base">Table</div>
							<FormControl type="select" :options="tables.map((table) => ({
								label: table,
								value: table,
							}))
								" size="sm" variant="outline" placeholder="Selected Table" v-model="selectedTable" />
							<Button variant="outline" theme="gray" size="sm"
								@click="this.showTypeColumn = !this.showTypeColumn"
								:iconLeft="this.showTypeColumn ? 'eye' : 'eye-off'">
								Query Type
							</Button>
							<Button variant="outline" theme="gray" size="sm"
								@click="this.showTableColumn = !this.showTableColumn"
								:iconLeft="this.showTableColumn ? 'eye' : 'eye-off'">
								Table Name
							</Button>
						</div>

						<div class="flex flex-row items-center gap-2">
							<FormControl type="text" size="sm" variant="outline" placeholder="Search keywords"
								v-model="searchString" :disabled="this.$resources?.searchBinlogs?.loading ||
									this.$resources?.fetchQueriesFromBinlog?.loading
									" />
							<Button variant="solid" theme="gray" size="sm" @click="searchBinlogs" :loading="this.$resources?.searchBinlogs?.loading ||
								this.$resources?.fetchQueriesFromBinlog?.loading
								" loadingText="Searching" iconLeft="search">
								Search
							</Button>
						</div>
					</div>
					<!-- Result Table -->
					<div class="mt-3">
						<div v-if="!this.searchResultReady"
							class="flex h-80 w-full items-center justify-center gap-2 text-base text-gray-700">
							Search for binlogs to see results
						</div>
						<div v-else-if="this.$resources?.searchBinlogs?.loading"
							class="flex h-80 w-full items-center justify-center gap-2 text-base text-gray-700">
							<Spinner class="w-4" /> Searching for binlogs...
						</div>
						<BinlogResultTable v-else :loadingData="this.$resources?.fetchQueriesFromBinlog?.loading"
							:loadData="this.fetchQueries" :columns="this.tableColumns" :data="this.tableRows"
							:isTruncateText="true" :truncateLength="120" :noOfRows="queryIds.length"
							:fullViewFormatters="fullViewFormatters" :cellFormatters="cellFormatters" :alignColumns="{
								'Event Size': 'center',
								Timestamp: 'center',
							}" />
					</div>

					<!-- Block  -->
					<div class="z-1000 bg-white-overlay-900 absolute inset-0 flex justify-center items-center"
						v-if="!isBinlogSearchAccessible">
						<div class="flex text-md text-gray-800 items-center gap-1.5">
							<lucide-triangle-alert class="h-5 w-5 text-amber-600" />
							To view or search SQL queries, choose a time range of less than 6
							hours
						</div>
					</div>
				</div>
			</div>
		</div>

		<!-- Overlay to hide controls while building timeline -->
		<div class="z-1000 bg-white-overlay-800 absolute inset-0 flex justify-center items-center"
			v-if="this.$resources?.timeline?.loading">
			<div class="flex gap-2 text-base text-gray-800">
				<Spinner class="w-4" />
				Building timeline...
			</div>
		</div>
	</div>
</template>
<script>
import BinlogBrowserChart from '../../../components/devtools/database/BinlogBrowserChart.vue';
import Header from '../../../components/Header.vue';
import { Tabs, Breadcrumbs, Select, FeatherIcon, Spinner } from 'frappe-ui';
import DatTimePicker from './extras/DateTimePicker.vue';
import { formatValue } from '../../../utils/format';
import LinkControl from '../../../components/LinkControl.vue';
import BinlogResultTable from '../../../components/devtools/database/BinlogResultTable.vue';

export default {
	name: 'BinlogBrowser',
	components: {
		Header,
		Breadcrumbs,
		Tabs,
		LinkControl,
		Select,
		BinlogResultTable,
		DatTimePicker,
		BinlogBrowserChart,
		Spinner,
	},
	data() {
		return {
			site: null,
			errorMessage: null,
			data: null,
			start: null,
			end: null,
			type: 'ALL',
			selectedTable: 'All Tables',
			searchString: '',
			queryIds: [],
			result: [],
			searchResultReady: false,
			showTypeColumn: false,
			showTableColumn: false,
			dateRangeValue: null,
			lastPushedState: null, // Track last pushed URL state
			searchSQLQueriesOnce: true,
		};
	},
	mounted() {
		this.loadFromURLParams();

		// Listen for browser back/forward button
		window.addEventListener('popstate', this.handlePopState);
	},
	beforeUnmount() {
		// Clean up event listener
		window.removeEventListener('popstate', this.handlePopState);
	},
	watch: {
		site(site_name) {
			if (!site_name) return;
			// set site to query param ?site=site_name
			this.updateURLParams();

			// reset state
			this.data = null;
			this.errorMessage = null;
			this.$resources.site.submit();
			this.fetchBinlogTimeline();
		},
		type() {
			this.fetchBinlogTimeline();
		},
		start() {
			this.updateURLParams();
			this.fetchBinlogTimeline();
		},
		end() {
			this.updateURLParams();
			this.fetchBinlogTimeline();
		},
	},
	resources: {
		site() {
			return {
				url: 'press.api.client.get',
				initialData: {},
				makeParams: () => {
					return { doctype: 'Site', name: this.site };
				},
				auto: false,
			};
		},
		timeline() {
			return {
				url: 'press.api.client.run_doc_method',
				initialData: {},
				auto: false,
				onSuccess: (data) => {
					if (data?.message) {
						this.resetSearch();
					}
				},
			};
		},
		searchBinlogs() {
			return {
				url: 'press.api.client.run_doc_method',
				initialData: {},
				auto: false,
				onSuccess: (data) => {
					if (data?.message) {
						this.queryIds = [];
						this.result = [];
						let rowIds = data?.message;
						let binlogs = Object.keys(rowIds).sort();
						for (let i = 0; i < binlogs.length; i++) {
							let binlogRowIds = rowIds[binlogs[i]];
							for (let j = 0; j < binlogRowIds.length; j++) {
								this.queryIds.push(`${binlogs[i]}:${binlogRowIds[j]}`);
							}
						}
						this.searchResultReady = true;
					}
				},
			};
		},
		fetchQueriesFromBinlog() {
			return {
				url: 'press.api.client.run_doc_method',
				initialData: {},
				auto: false,
				onSuccess: (data) => {
					if (data?.message) {
						let binlogs = Object.keys(data.message);
						binlogs.sort();
						this.result = [];
						for (let i = 0; i < binlogs.length; i++) {
							let binlogRowIds = Object.keys(data.message[binlogs[i]]);
							binlogRowIds.sort();
							for (let j = 0; j < binlogRowIds.length; j++) {
								let queryInfo = data.message[binlogs[i]][binlogRowIds[j]];
								this.result.push([
									queryInfo[1],
									queryInfo[4],
									queryInfo[0],
									new Date(queryInfo[5] * 1000).toLocaleString(),
									queryInfo[2],
								]);
							}
						}
					}
				},
			};
		},
	},
	methods: {
		loadFromURLParams() {
			const url = new URL(window.location.href);
			const site_name = url.searchParams.get('site');
			const startParam = url.searchParams.get('start');
			const endParam = url.searchParams.get('end');

			// Load from query params if available
			if (startParam && endParam) {
				const startDate = new Date(parseInt(startParam) * 1000);
				const endDate = new Date(parseInt(endParam) * 1000);
				this.start = startDate.toLocaleString();
				this.end = endDate.toLocaleString();
			} else {
				// Default to last 24 hours
				const now = new Date();
				this.end = now.toLocaleString();
				const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
				this.start = oneDayAgo.toLocaleString();
			}

			if (site_name) {
				this.site = site_name;
			}

			// Initialize lastPushedState with current URL
			this.lastPushedState = window.location.href;
		},
		handlePopState() {
			// When user clicks back/forward, reload from URL without triggering watchers
			const url = new URL(window.location.href);
			const site_name = url.searchParams.get('site');
			const startParam = url.searchParams.get('start');
			const endParam = url.searchParams.get('end');

			if (startParam && endParam) {
				const startDate = new Date(parseInt(startParam) * 1000);
				const endDate = new Date(parseInt(endParam) * 1000);
				this.start = startDate.toLocaleString();
				this.end = endDate.toLocaleString();
			}

			if (site_name) {
				this.site = site_name;
			}
		},
		updateURLParams() {
			const url = new URL(window.location.href);

			if (this.site) {
				url.searchParams.set('site', this.site);
			}

			if (this.start && this.end) {
				const startTimestamp = parseInt(new Date(this.start).getTime() / 1000);
				const endTimestamp = parseInt(new Date(this.end).getTime() / 1000);
				url.searchParams.set('start', startTimestamp);
				url.searchParams.set('end', endTimestamp);
			}

			// Only push state if it's different from the last pushed state
			const newState = url.toString();
			if (this.lastPushedState !== newState) {
				window.history.pushState({}, '', url);
				this.lastPushedState = newState;
			}
		},
		fetchBinlogTimeline() {
			if (!this.start || !this.end || !this.site) return;
			if (this.$resources.timeline?.loading ?? true) return;
			this.$resources.timeline.submit({
				dt: 'Site',
				dn: this.site,
				method: 'fetch_binlog_timeline',
				args: {
					start: parseInt(new Date(this.start).getTime() / 1000),
					end: parseInt(new Date(this.end).getTime() / 1000),
					query_type: this.type === 'ALL' ? null : this.type,
				},
			});
		},
		searchBinlogs() {
			this.$resources.searchBinlogs.submit({
				dt: 'Site',
				dn: this.site,
				method: 'search_binlogs',
				args: {
					start: parseInt(new Date(this.start).getTime() / 1000),
					end: parseInt(new Date(this.end).getTime() / 1000),
					query_type: this.type === 'ALL' ? null : this.type,
					table:
						this.selectedTable === 'All Tables' ? null : this.selectedTable,
					search_string: this.searchString,
				},
			});
		},
		fetchQueries(start, end) {
			let lastQueryIndex = this.result.length;
			if (lastQueryIndex >= this.queryIds.length) {
				return;
			}
			if (this.$resources.fetchQueriesFromBinlog?.loading ?? true) return;

			// Load 50 queries at a time
			const queriesToLoad = this.queryIds.slice(start, end);
			let rowIds = {};
			queriesToLoad.forEach((q) => {
				const [binlog, rowId] = q.split(':');
				if (!rowIds[binlog]) {
					rowIds[binlog] = [];
				}
				rowIds[binlog].push(parseInt(rowId));
			});

			if (Object.keys(rowIds).length > 0) {
				this.$resources.fetchQueriesFromBinlog.submit({
					dt: 'Site',
					dn: this.site,
					method: 'fetch_queries_from_binlog',
					args: {
						row_ids: rowIds,
					},
				});
			}
		},
		onZoomEvent(start, end) {
			if (!start || !end) {
				return;
			}
			this.start = null;
			this.end = null;
			this.start = start['timestamp'].toLocaleString();
			this.end = end['timestamp'].toLocaleString();
		},
		resetSearch() {
			this.queryIds = [];
			this.result = [];
			this.searchResultReady = false;
			if (this.isBinlogSearchAccessible) {
				this.searchBinlogs();
			}
		},
	},
	computed: {
		isRequiredInformationReceived() {
			if (this.$resources.site?.loading ?? true) return false;
			return true;
		},

		timeline() {
			return this.$resources?.timeline?.data?.message ?? {};
		},
		tables() {
			return ['All Tables', ...(this.timeline?.tables ?? [])];
		},
		barChartData() {
			if (!this.timeline?.dataset) {
				return [];
			}
			// Convert the timestamp to Date
			const convertedDataset = this.timeline.dataset.map((entry) => {
				const date = new Date(entry.timestamp * 1000);
				return {
					...entry,
					timestamp: date,
				};
			});

			return convertedDataset;
		},
		tableColumns() {
			let columns = ['Type', 'Table', 'Query', 'Timestamp', 'Event Size'];
			if (!this.showTypeColumn && !this.showTableColumn) {
				columns = columns.slice(2);
			} else if (!this.showTypeColumn) {
				columns = columns.slice(1);
			} else if (!this.showTableColumn) {
				columns = columns.filter((col) => col !== 'Table');
			}
			return columns;
		},
		tableRows() {
			if (!this.result) return [];
			let result = this.result;
			if (!this.showTypeColumn && !this.showTableColumn) {
				result = result.map((row) => row.slice(2));
			} else if (!this.showTypeColumn) {
				result = result.map((row) => [row[1], row[2], row[3]]);
			} else if (!this.showTableColumn) {
				result = result.map((row) => [row[0], row[2], row[3]]);
			}
			return result;
		},
		cellFormatters() {
			return {
				'Event Size': (v) => formatValue(v, 'bytes'),
			};
		},
		fullViewFormatters() {
			return {
				Query: (v) => formatValue(v, 'sql'),
			};
		},
		isBinlogSearchAccessible() {
			if (!this.site || !this.start || !this.end) {
				return false;
			}
			// Ensure the selected time range is <= 6 hours
			const startTime = new Date(this.start).getTime();
			const endTime = new Date(this.end).getTime();
			const sixHoursInMs = 6 * 60 * 60 * 1000;
			return endTime - startTime <= sixHoursInMs;
		},
	},
};
</script>

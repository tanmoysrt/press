<template>
	<div
		ref="chartDiv"
		v-show="!error"
		class="h-full w-full min-w-[300px] md:min-w-[400px] min-h-[300px]"
	></div>
	<div
		v-show="error"
		class="flex h-full w-full items-center justify-center text-center text-red-500"
	>
		Error: {{ error }}
	</div>
</template>

<script setup>
import { init } from 'echarts';
import { computed, ref, onMounted, onBeforeUnmount, watch } from 'vue';
import useAxisChartOptions from 'frappe-ui/src/components/Charts/axisChartOptions';

const props = defineProps({
	data: {
		type: Array,
		required: true,
	},
	onZoomEvent: {
		type: Function,
		required: false,
	},
});

const error = ref('');
const options = computed(() => {
	try {
		return useAxisChartOptions({
			data: props.data,
			xAxis: {
				key: 'timestamp',
				type: 'time',
				title: 'Day',
				timeGrain: 'minute',
			},
			yAxis: {
				title: 'Count',
			},
			stacked: true,
			series: [
				{ name: 'INSERT', type: 'bar' },
				{ name: 'UPDATE', type: 'bar' },
				{ name: 'DELETE', type: 'bar' },
				{ name: 'SELECT', type: 'bar' },
				{ name: 'OTHER', type: 'bar' },
			],
			echartOptions: {
				legend: { show: false },
				dataZoom: [
					{
						type: 'slider',
						xAxisIndex: 0,
						bottom: 15,
						height: 30,
						realtime: true,
						showDetail: true,
					},
				],
			},
		});
	} catch (e) {
		error.value = e.message;
		return {};
	}
});

let chart;
const chartDiv = ref();

function debounce(func, wait) {
	let timeout;
	return function executedFunction(...args) {
		const later = () => {
			clearTimeout(timeout);
			func(...args);
		};
		clearTimeout(timeout);
		timeout = setTimeout(later, wait);
	};
}

function onZoomEventHandler(zoom) {
	if (!props.onZoomEvent) {
		return;
	}

	const startPercent = zoom.start;
	const endPercent = zoom.end;

	if (!props.data || props.data.length < 2) {
		return;
	}

	const data = props.data;
	const len = props.data.length;

	const startIndex = Math.floor((startPercent / 100) * (len - 1));
	const endIndex = Math.floor((endPercent / 100) * (len - 1));

	props.onZoomEvent && props.onZoomEvent(data[startIndex], data[endIndex]);
}

const onZoomEventHandlerDebounced = debounce(onZoomEventHandler, 1000);

onMounted(() => {
	if (!chartDiv.value) return;

	chart = init(chartDiv.value, 'light', { renderer: 'svg' });
	chart.setOption({ ...options.value }, true);

	chart.on('datazoom', function (zoom) {
		onZoomEventHandlerDebounced(zoom);
	});

	const resizeDebounce = debounce(() => {
		chart.resize({
			animation: {
				duration: 300,
			},
		});
	}, 250);

	let resizeObserver = new ResizeObserver(resizeDebounce);
	setTimeout(() => resizeObserver.observe(chartDiv.value), 500);
	onBeforeUnmount(() => resizeObserver.unobserve(chartDiv.value));
});

watch(
	() => options.value,
	(newOptions) => {
		if (chart) {
			chart.setOption(newOptions, true);
		}
	},
	{ deep: true },
);
</script>

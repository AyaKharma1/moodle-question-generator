<script setup lang="ts">
// Small line icons (24x24, drawn with currentColor) so no emoji is needed.
defineProps<{ name: string }>();
const paths: Record<string, string> = {
  critical: "M7.9 2h8.2L22 7.9v8.2L16.1 22H7.9L2 16.1V7.9L7.9 2z M15 9l-6 6 M9 9l6 6",
  review: "M12 3l10 18H2L12 3z M12 10v4 M12 17.5v.01",
  info: "M12 22a10 10 0 100-20 10 10 0 000 20z M12 16v-5 M12 7.5v.01",
  check: "M12 22a10 10 0 100-20 10 10 0 000 20z M8 12.5l3 3 5-6",
  file: "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z M14 2v6h6",
  folder: "M3 6a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V6z",
  book: "M4 19.5A2.5 2.5 0 016.5 17H20V3H6.5A2.5 2.5 0 004 5.5v14z M4 19.5A2.5 2.5 0 006.5 22H20v-5",
  download: "M12 3v12 M7 11l5 5 5-5 M4 21h16",
  upload: "M12 16V4 M7 8l5-5 5 5 M4 21h16",
  inbox: "M22 12h-6l-2 3h-4l-2-3H2 M5.5 5h13l3.5 7v6a2 2 0 01-2 2H4a2 2 0 01-2-2v-6l3.5-7z",
  search: "M11 19a8 8 0 100-16 8 8 0 000 16z M21 21l-4.3-4.3",
  target: "M12 22a10 10 0 100-20 10 10 0 000 20z M12 18a6 6 0 100-12 6 6 0 000 12z M12 14a2 2 0 100-4 2 2 0 000 4z",
  image: "M5 3h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2z M8.5 10a1.5 1.5 0 100-3 1.5 1.5 0 000 3z M21 15l-5-5L5 21",
  sparkle: "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3z M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16z",
};
</script>

<template>
  <svg class="icon-svg" viewBox="0 0 24 24" width="1.1em" height="1.1em" fill="none" stroke="currentColor"
       stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path :d="paths[name] ?? paths.info" />
  </svg>
</template>

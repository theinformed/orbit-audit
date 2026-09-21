// Build-time source only. Readers receive HTML, never this module or its dependencies.
import { CHAPTERS, satelliteFundamentalsPageView } from '../src/satellite-fundamentals';
import { WEATHER_MODULE_IDS, weatherLessonView } from '../src/content';

export function studyPages(): Array<{ id: string; html: string }> {
  return [
    ...CHAPTERS.map(chapter => ({ id: `satellite-${chapter.id}`, html: satelliteFundamentalsPageView(chapter.id) })),
    ...WEATHER_MODULE_IDS.map(id => ({ id: `weather-${id}`, html: weatherLessonView(id) })),
  ];
}

import { Button } from '@/components/ui/button'
import { cn } from 'cn'
import { supportsMusicPage } from '@/features/music/source-capabilities'
import { useMusicSources } from '@/features/music/use-music-sources'
import { useMusicNavigation, type MusicView } from './music-navigation'

const desktopPages = [
  ['library', '音乐库'],
  ['discover', '发现'],
  ['local', '本地']
] as const

const mobilePages = [
  ['library', '音乐库'],
  ['discover', '发现'],
  ['search', '搜索'],
  ['local', '本地']
] as const

function isSelected(view: MusicView, current: MusicView, mobile = false) {
  return (
    current === view ||
    (view === 'library' &&
      (current === 'collection' || current === 'streaming-playlist' || current === 'accounts')) ||
    (!mobile && view === 'discover' && current === 'search') ||
    (view === 'search' && current === 'search') ||
    (view === 'local' && (current.startsWith('local-') || current === 'aggregate-playlist'))
  )
}

export function MusicNavButtons({ mobile = false }: { mobile?: boolean } = {}) {
  const sources = useMusicSources()
  const current = sources.statuses.find(
    (item) => item.descriptor.source === sources.preferences?.current && item.enabled
  )
  const { page, navigate } = useMusicNavigation()
  const pages = mobile ? mobilePages : desktopPages
  return pages.map(([view, label]) => {
    const supported =
      view === 'local' ||
      view === 'search' ||
      supportsMusicPage(current?.descriptor, view as 'library' | 'discover')
    const selected = isSelected(view, page.view, mobile)
    return (
      <Button
        key={view}
        disabled={!supported}
        title={supported ? undefined : `此适配器未提供${label}`}
        variant="ghost"
        className={cn(
          'cursor-pointer',
          mobile && 'mobile-navigation-item',
          selected && 'text-[var(--music-accent)] hover:text-[var(--music-accent)]'
        )}
        aria-current={selected ? 'page' : undefined}
        onClick={() => navigate(view)}
      >
        {label}
      </Button>
    )
  })
}

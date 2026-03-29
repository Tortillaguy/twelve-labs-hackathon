export const HERO_MAP: Record<number, string> = {
  1: "Anti-Mage", 2: "Axe", 3: "Bane", 4: "Bloodseeker", 5: "Crystal Maiden",
  6: "Drow Ranger", 7: "Earthshaker", 8: "Juggernaut", 9: "Mirana", 10: "Morphling",
  11: "Nevermore", 12: "Phantom Lancer", 13: "Puck", 14: "Pudge", 15: "Razor",
  16: "Sand King", 17: "Storm Spirit", 18: "Sven", 19: "Tiny", 20: "Vengeful Spirit",
  21: "Windranger", 22: "Zeus", 23: "Kunkka", 25: "Lina", 26: "Lion",
  27: "Shadow Shaman", 28: "Slardar", 29: "Tidehunter", 30: "Witch Doctor", 31: "Lich",
  32: "Riki", 33: "Enigma", 34: "Tinker", 35: "Sniper", 36: "Necrophos",
  37: "Warlock", 38: "Beastmaster", 39: "Queen of Pain", 40: "Venomancer", 41: "Faceless Void",
  42: "Skeleton King", 43: "Death Prophet", 44: "Phantom Assassin", 45: "Pugna", 46: "Templar Assassin",
  47: "Viper", 48: "Luna", 49: "Dragon Knight", 50: "Dazzle", 51: "Clockwerk",
  52: "Leshrac", 53: "Nature's Prophet", 54: "Lifestealer", 55: "Dark Seer", 56: "Clinkz",
  57: "Omniknight", 58: "Enchantress", 59: "Huskar", 60: "Night Stalker", 61: "Broodmother",
  62: "Bounty Hunter", 63: "Weaver", 64: "Jakiro", 65: "Batrider", 66: "Chen",
  67: "Spectre", 68: "Ancient Apparition", 69: "Doom Bringer", 70: "Ursa", 71: "Spirit Breaker",
  72: "Gyrocopter", 73: "Alchemist", 74: "Invoker", 75: "Silencer", 76: "Outworld Destroyer",
  77: "Lycan", 78: "Brewmaster", 79: "Shadow Demon", 80: "Lone Druid", 81: "Chaos Knight",
  82: "Meepo", 83: "Treant Protector", 84: "Ogre Magi", 85: "Undying", 86: "Rubick",
  87: "Disruptor", 88: "Nyx Assassin", 89: "Naga Siren", 90: "Keeper of the Light", 91: "Io",
  92: "Visage", 93: "Slark", 94: "Medusa", 95: "Troll Warlord", 96: "Centaur Warrunner",
  97: "Magnus", 98: "Timbersaw", 99: "Bristleback", 100: "Tusk", 101: "Skywrath Mage",
  102: "Abaddon", 103: "Elder Titan", 104: "Legion Commander", 105: "Techies", 106: "Ember Spirit",
  107: "Earth Spirit", 108: "Underlord", 109: "Terrorblade", 110: "Phoenix", 111: "Oracle",
  112: "Winter Wyvern", 113: "Arc Warden", 114: "Monkey King", 119: "Dark Willow", 120: "Pangolier",
  121: "Grimstroke", 123: "Hoodwink", 126: "Void Spirit", 128: "Snapfire", 129: "Mars",
  135: "Dawnbreaker", 136: "Marci", 137: "Primal Beast", 138: "Muerta", 145: "Kez"
};

export function getHeroName(id: number): string {
  return HERO_MAP[id] || `Hero ${id}`;
}

// CDN slug map — most are display-name-to-snake-case, overrides handle legacy internal names
const SLUG_OVERRIDES: Record<number, string> = {
  1:   'antimage',           // Anti-Mage → compressed
  11:  'nevermore',          // Shadow Fiend legacy name
  21:  'windrunner',         // Windranger legacy name
  22:  'zuus',               // Zeus legacy name
  39:  'queenofpain',        // no underscores
  42:  'skeleton_king',      // Wraith King legacy name
  51:  'rattletrap',         // Clockwerk legacy name
  53:  'furion',             // Nature's Prophet legacy name
  54:  'life_stealer',       // extra underscore
  69:  'doom',               // Doom Bringer shortened
  76:  'obsidian_destroyer', // Outworld Destroyer legacy name
  90:  'keeper_of_the_light',
  91:  'wisp',               // Io legacy name
  108: 'abyssal_underlord',  // Underlord full internal name
}

function toSlug(name: string): string {
  return name.toLowerCase().replace(/['']/g, '').replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '')
}

export const HERO_SLUG_MAP: Record<number, string> = Object.fromEntries(
  Object.entries(HERO_MAP).map(([id, name]) => {
    const numId = Number(id)
    return [numId, SLUG_OVERRIDES[numId] ?? toSlug(name)]
  })
)

export function getHeroSlug(id: number): string | null {
  return HERO_SLUG_MAP[id] ?? null
}

export function getHeroImageUrl(id: number): string | null {
  const slug = getHeroSlug(id)
  return slug
    ? `https://cdn.cloudflare.steamstatic.com/apps/dota2/images/dota_react/heroes/${slug}.png`
    : null
}

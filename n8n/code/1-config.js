// EVERYTHING YOU MAY WANT TO CHANGE IS IN THIS NODE.
return [{ json: {
  // Your GitHub user name and the repository that holds the feed
  owner: 'YOUR_GITHUB_USERNAME',
  repo: 'examprep-feed',
  branch: 'main',

  // The Claude model. claude-opus-5-5 writes the best notes and MCQs.
  // claude-sonnet-5-5 costs about half as much, claude-haiku-5-5 far less.
  model: 'claude-opus-5-5',

  hoursBack: 30,     // only stories published in the last 30 hours
  minPicks: 8,       // news cards per day, between these two numbers
  maxPicks: 15,
  minMcqs: 15,       // MCQs per day, between these two numbers
  maxMcqs: 30,

  // FULL TEXT. false = a must-read card shows ExamPrep's own summary and a link to the paper.
  // true = the card shows the paper's article word for word, under the paper's name and logo.
  // Switch a paper to true only from the day your signed agreement with it starts.
  // (Foreign Affairs puts only one line in its feed, so it has no full text to show.)
  fullText: {
    'Dawn': false,
    'The Express Tribune': false,
    'Foreign Affairs': false,
  },

  // Preferred sources first. Add or remove a line to change what is read.
  feeds: [
    { source: 'Dawn',               section: 'Editorial & Opinion', url: 'https://www.dawn.com/feeds/opinion' },
    { source: 'Dawn',               section: 'Front page',          url: 'https://www.dawn.com/feeds/home' },
    { source: 'Dawn',               section: 'National',            url: 'https://www.dawn.com/feeds/pakistan' },
    { source: 'Dawn',               section: 'International',       url: 'https://www.dawn.com/feeds/world' },
    { source: 'Dawn',               section: 'Business',            url: 'https://www.dawn.com/feeds/business' },
    { source: 'The Express Tribune', section: 'Editorial',          url: 'https://tribune.com.pk/feed/editorial' },
    { source: 'The Express Tribune', section: 'Opinion',            url: 'https://tribune.com.pk/feed/opinion' },
    { source: 'The Express Tribune', section: 'National',           url: 'https://tribune.com.pk/feed/pakistan' },
    { source: 'The Express Tribune', section: 'International',      url: 'https://tribune.com.pk/feed/world' },
    { source: 'The Express Tribune', section: 'Business',           url: 'https://tribune.com.pk/feed/business' },
    { source: 'Foreign Affairs',    section: 'Analysis',            url: 'https://www.foreignaffairs.com/rss.xml' },
  ],
} }];

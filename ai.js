const axios = require('axios');

async function askOpenAI(prompt) {
  const response = await axios.post('https://api.openai.com/v1/chat/completions', {
    model: 'gpt-3.5-turbo',
    messages: [{ role: 'user', content: prompt }]
  }, {
    headers: { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` }
  });

  return response.data.choices[0].message.content;
}

async function askHuggingFace(prompt) {
  const response = await axios.post('https://api-inference.huggingface.co/models/gpt2', {
    inputs: prompt
  }, {
    headers: { Authorization: `Bearer ${process.env.HUGGINGFACE_API_KEY}` }
  });

  return response.data[0]?.generated_text || 'לא התקבלה תשובה';
}

module.exports = { askOpenAI, askHuggingFace };

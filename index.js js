require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
const { sendToken } = require('./distribute');
const { saveUser, getUsers } = require('./users');
const { saveContract } = require('./contracts');
const { logDistribution } = require('./history');
const { askOpenAI, askHuggingFace } = require('./ai');

const bot = new TelegramBot(process.env.TELEGRAM_BOT_TOKEN, { polling: true });

bot.onText(/\/wallet (.+)/, (msg, match) => {
  saveUser(msg.chat.id, match[1]);
  bot.sendMessage(msg.chat.id, `✅ כתובת הארנק שלך נשמרה`);
});

bot.onText(/\/contract (.+)/, (msg, match) => {
  saveContract(msg.chat.id, match[1]);
  bot.sendMessage(msg.chat.id, `✅ כתובת החוזה שלך נשמרה`);
});

bot.onText(/\/distribute (\d+)/, async (msg, match) => {
  const amount = match[1];
  const users = getUsers();

  for (const userId in users) {
    const wallet = users[userId];
    try {
      const receipt = await sendToken(wallet, amount);
      logDistribution(wallet, amount, receipt.transactionHash);
      bot.sendMessage(userId, `🎉 קיבלת ${amount} טוקנים`);
    } catch (err) {
      bot.sendMessage(userId, `❌ שגיאה: ${err.message}`);
    }
  }

  bot.sendMessage(msg.chat.id, `✅ חלוקה הושלמה`);
});

bot.onText(/\/askai (.+)/, async (msg, match) => {
  const prompt = match[1];
  const reply = await askOpenAI(prompt);
  bot.sendMessage(msg.chat.id, reply);
});

bot.onText(/\/huggingface (.+)/, async (msg, match) => {
  const prompt = match[1];
  const reply = await askHuggingFace(prompt);
  bot.sendMessage(msg.chat.id, reply);
});

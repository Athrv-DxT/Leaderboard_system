import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import { getAuth, signInWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import { 
  getFirestore, collection, setDoc, deleteDoc, doc, getDocs, updateDoc, increment, query, orderBy 
} from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyD_9El1Ivnv_t-VafCuOHQTeAehPL0KQ3c",
  authDomain: "funfinity-c3cb4.firebaseapp.com",
  projectId: "funfinity-c3cb4",
  storageBucket: "funfinity-c3cb4.firebasestorage.app",
  messagingSenderId: "623442330452",
  appId: "1:623442330452:web:3d6a683d573cd7ce947ec1"
};

// Init Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);

window.login = async function () {
  const email = document.getElementById("email").value;
  const password = document.getElementById("password").value;

  try {
    await signInWithEmailAndPassword(auth, email, password);
    document.getElementById("login-section").style.display = "none";
    document.getElementById("admin-section").style.display = "block";
    loadPlayers();
  } catch (error) {
    alert("Login failed: " + error.message);
  }
};

document.getElementById("playerForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = document.getElementById("playerName").value;

  await setDoc(doc(db, "players", name), { name, score: 0 }, { merge: true });
  loadPlayers();
});

async function loadPlayers() {
  const list = document.getElementById("playerList");
  list.innerHTML = "";

  // sort players by score desc
  const q = query(collection(db, "players"), orderBy("score", "desc"));
  const querySnapshot = await getDocs(q);

  let rank = 1;
  querySnapshot.forEach((docSnap) => {
    const player = docSnap.data();
    const li = document.createElement("li");

    li.innerHTML = `
      <span>#${rank} <strong>${player.name}</strong> — ${player.score}</span>
      <div>
        <button onclick="updateScore('${player.name}', 10)">+10</button>
        <button onclick="updateScore('${player.name}', -10)">-10</button>
        <input type="number" id="custom-${player.name}" placeholder="± Score" style="width:70px">
        <button onclick="customUpdate('${player.name}')">Apply</button>
        <button style="background:#444" onclick="deletePlayer('${player.name}')">❌</button>
      </div>
    `;

    list.appendChild(li);
    rank++;
  });
}

window.updateScore = async function (playerName, change) {
  const ref = doc(db, "players", playerName);
  await updateDoc(ref, { score: increment(change) });
  loadPlayers();
};

window.customUpdate = async function (playerName) {
  const input = document.getElementById(`custom-${playerName}`);
  const value = parseInt(input.value);

  if (!isNaN(value) && value !== 0) {
    const ref = doc(db, "players", playerName);
    await updateDoc(ref, { score: increment(value) });
    loadPlayers();
    input.value = ""; // clear after update
  } else {
    alert("Enter a valid number!");
  }
};

window.deletePlayer = async function (playerName) {
  await deleteDoc(doc(db, "players", playerName));
  loadPlayers();
};

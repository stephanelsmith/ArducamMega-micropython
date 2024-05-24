

let app = Vue.createApp({
    template: `
        <snap_section v-for='snap in snaps'
            v-bind:img_src=snap.img_src
            >
        </snap_section>
    `,
    props: {
    },
    data: function(){
        return {
            snaps : [],
			//mqtt_uri : 'wss://test.mosquitto.org:8081',
			mqtt_uri : 'wss://broker.hivemq.com:8884/mqtt',
            mqtt_client : null,
        };
    },
    watch: {
    },
    methods:{
        add_snap: function(){
            this.snaps.push({
                img_src : 'data:image/jpg;base64,'+'iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4',
            });
        },
        mqtt_connect: async function(){
			let self = this;
            console.log('connecting to broker...', self.mqtt_uri);
            self.mqtt_client = await mqtt.connectAsync(self.mqtt_uri);
            console.log('connected to broker', self.mqtt_uri);
            await self.mqtt_client.subscribeAsync('sscam/pix/#');
			self.mqtt_client.on('message', function(topic, message){
                // self.b64 = message.toString(); // if sending directly b64

				// if we sent binary instead
				let b = message.reduce((data, byte)=> {
					return data + String.fromCharCode(byte);
				}, '');
				let b64 = btoa(b);
                //self.add_snap();
                let snap = _.last(self.snaps);
                snap.img_src = 'data:image/jpg;base64,'+b64;
			});
        },
    },
    computed:{
    },
    created: function(){
    },
    mounted: function(){
        this.mqtt_connect();
        this.add_snap();
    },
    delimiters: ['[[', ']]'],
});
app.mount('#app');

app.component('snap_section', {
    template: `
        <div>
            hello snap
            <img v-bind:src=img_src>
        </div>
    `,
    props: {
        img_src : String,
    },
    data: function(){
        return {
        };
    },
    watch: {
    },
    methods:{
    },
    computed:{
    },
    created: function(){
    },
    mounted: function(){
        console.log('MOUNTED COMP');
    },
    delimiters: ['[[', ']]'],
})



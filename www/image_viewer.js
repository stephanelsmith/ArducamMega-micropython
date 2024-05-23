

Vue.createApp({
    template: `
        <div>
            <img v-bind:src=img_src>
        </div>
    `,
    props: {
    },
    data: function(){
        return {
			//mqtt_uri : 'wss://test.mosquitto.org:8081',
			mqtt_uri : 'wss://broker.hivemq.com:8884/mqtt',

            mqtt_client : null,
			b64 : 'iVBORw0KGgoAAAANSUhEUgAAAAUAAAAFCAYAAACNbyblAAAAHElEQVQI12P4',
        };
    },
    watch: {
    },
    methods:{
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
				self.b64 = btoa(b);
			});
        },
    },
    computed:{
        img_src : function(){
            return 'data:image/jpg;base64,'+this.b64;
        },
    },
    created: function(){
    },
    mounted: function(){
        this.mqtt_connect();
    },
    delimiters: ['[[', ']]'],
}).mount('#app');

